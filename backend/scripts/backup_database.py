"""Zamanlanmış tam veritabanı yedeği (İBYS Yedekleme Prosedürü).

Davranış:

- PostgreSQL için ``pg_dump --format=custom``; SQLite için dosya kopyası.
- Production'da şifreleme zorunludur (fail-closed): anahtar yok/zayıf ise yedek
  üretilmez, süreç hata koduyla biter.
- Yedek ``BACKUP_DIR`` altına yazılır; ``BACKUP_REMOTE_ENABLED`` açıksa
  boyut + SHA-256 doğrulanmış offsite (R2/S3) kopya da alınır.
- Süresi dolan yedekler GFS (günlük/haftalık/aylık) ile temizlenir.
- Sonuç her zaman stdout'a tek satır JSON olarak basılır (cron izleme).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse

from app.core.config import settings

logger = logging.getLogger(__name__)


class BackupError(RuntimeError):
    """Yedek üretimi güvenli biçimde durdurulduğunda kullanılır."""


def backup_sqlite(database_url: str, target: Path) -> Path:
    source = Path(database_url.removeprefix("sqlite:///")).resolve()
    if not source.exists():
        raise BackupError(f"SQLite veritabanı bulunamadı: {source}")
    output = target.with_suffix(".db")
    shutil.copy2(source, output)
    return output


def _safe_pg_url(database_url: str) -> tuple[str, str]:
    """pg_dump için parolasız URL ve ayrı parola döndürür."""
    parsed = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://"))
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    password = unquote(parsed.password or "") or next(
        (unquote(value) for key, value in query_items if key.casefold() == "password"),
        "",
    )
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    if parsed.username:
        netloc = f"{quote(unquote(parsed.username), safe='')}@{netloc}"
    query = urlencode(
        [(key, value) for key, value in query_items if key.casefold() != "password"]
    )
    safe_url = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, query, ""))
    return safe_url, password


def backup_postgresql(database_url: str, target: Path) -> Path:
    if shutil.which("pg_dump") is None:
        raise BackupError(
            "pg_dump bulunamadı. PostgreSQL istemci araçlarını kurun "
            "(postgresql-client) ve PATH'e ekleyin."
        )
    safe_url, password = _safe_pg_url(database_url)
    output = target.with_suffix(".dump")
    command = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file", str(output),
        safe_url,
    ]
    env = dict(os.environ)
    if password:
        # Parola argv'ye değil ortam değişkenine verilir (P1-12).
        env["PGPASSWORD"] = password
    try:
        subprocess.run(command, check=True, env=env, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip().splitlines()
        hint = detail[-1] if detail else "pg_dump başarısız."
        raise BackupError(f"pg_dump başarısız: {hint[:300]}") from exc
    if not output.is_file() or output.stat().st_size == 0:
        raise BackupError("pg_dump çıktısı üretilmedi veya boş.")
    return output


def _encrypt_backup(produced: Path) -> Path:
    """Yedeği Fernet ile şifreler; düz dosyayı siler."""
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    from app.services.backup_restore import backup_encryption_key_material

    key = backup_encryption_key_material()
    if not key:
        raise BackupError("Şifreleme anahtarı yok.")
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    enc = produced.with_suffix(produced.suffix + ".enc")
    enc.write_bytes(Fernet(base64.urlsafe_b64encode(digest)).encrypt(produced.read_bytes()))
    produced.unlink(missing_ok=True)
    return enc


def _is_production() -> bool:
    return (settings.environment or "").strip().lower() in ("production", "prod", "live")


def _resolve_encryption() -> tuple[bool, str]:
    """(şifreleme yapılacak mı, anahtar durumu) — production'da fail-closed."""
    from app.services.backup_restore import (
        backup_encryption_key_status,
        enable_backup_crypto_for_production,
    )

    if _is_production():
        # SECRET_KEY türeviyle güvenli şifrelemeyi açmayı dene.
        enable_backup_crypto_for_production()
    status = backup_encryption_key_status()
    if status in ("dedicated", "secret_key_fallback"):
        return True, status
    if _is_production():
        raise BackupError(
            "Production'da yedek şifrelemesi zorunludur fakat anahtar durumu "
            f"'{status}'. BACKUP_ENCRYPTION_KEY tanımlayın (en az 32 karakter, rastgele)."
        )
    return False, status


def run_backup() -> dict:
    """Tek bir yedek üretir, doğrular, offsite kopyalar ve retention uygular."""
    from app.services.backup_management import (
        BackupOffsiteError,
        purge_expired_database_backups,
        upload_backup_to_offsite,
    )

    backup_dir = Path(settings.backup_dir).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"isgsuite-{stamp}"

    if settings.database_url.startswith("sqlite"):
        produced = backup_sqlite(settings.database_url, target)
    elif settings.database_url.startswith(("postgresql", "postgres")):
        produced = backup_postgresql(settings.database_url, target)
    else:
        raise BackupError("Desteklenmeyen veritabanı türü.")

    encrypt, key_status = _resolve_encryption()
    if encrypt:
        produced = _encrypt_backup(produced)

    result: dict = {
        "status": "ok",
        "file": produced.name,
        "path": str(produced),
        "size_bytes": produced.stat().st_size,
        "encrypted": encrypt,
        "encryption_key_status": key_status,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    try:
        offsite = upload_backup_to_offsite(produced)
    except BackupOffsiteError as exc:
        # Offsite kopya doğrulanamadı. Yerel yedek korunur; zorunlu moddaysa
        # yedek başarısız sayılır (fail-closed). Zorunlu değilse canlı düşmez
        # ama alarm üretilir — sessiz kalmaz.
        if bool(getattr(settings, "backup_remote_required", False)):
            raise BackupError(f"Offsite yedek doğrulanamadı: {exc}") from exc
        logger.error("Offsite yedek doğrulanamadı; yerel kopya korundu: %s", exc)
        offsite = {"uploaded": False, "reason": "verify-failed"}
    result["offsite"] = offsite
    if not offsite.get("uploaded") and bool(getattr(settings, "backup_remote_required", False)):
        raise BackupError("Offsite yedek zorunlu fakat yüklenemedi.")
    if not offsite.get("uploaded") and offsite.get("reason") == "verify-failed":
        from app.services.backup_management import notify_global_admins

        notify_global_admins(
            title="Offsite yedek doğrulanamadı",
            message=(
                f"Günlük veritabanı yedeği yerelde oluşturuldu ({produced.name}) ancak "
                "R2/S3 offsite kopyası boyut/checksum doğrulamasından geçemedi. "
                "3-2-1 yedeklilik şu an eksik; depolama erişimini kontrol edin."
            ),
            entity_type="backup_offsite_failure",
            entity_id=datetime.utcnow().strftime("%Y-%m-%d"),
        )

    retention = purge_expired_database_backups()
    result["retention"] = {
        "kept": retention.kept,
        "deleted": retention.deleted,
        "failed": retention.failed,
        "deleted_files": retention.deleted_files[:50],
    }
    return result


def main() -> int:
    try:
        result = run_backup()
    except Exception as exc:  # noqa: BLE001 - cron için tek satır JSON gerekir
        logger.exception("Günlük veritabanı yedeği başarısız: %s", type(exc).__name__)
        try:
            from app.services.backup_management import notify_global_admins

            notify_global_admins(
                title="Günlük veritabanı yedeği başarısız",
                message=(
                    f"Zamanlanmış tam veritabanı yedeği alınamadı: "
                    f"{type(exc).__name__} — {str(exc)[:300]}. "
                    "RPO riski oluşabilir; yedekleme altyapısını kontrol edin."
                ),
                entity_type="backup_failure",
                entity_id=datetime.utcnow().strftime("%Y-%m-%d"),
            )
        except Exception:  # pragma: no cover - alarm asla çıktıyı bozmaz
            pass
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_class": type(exc).__name__,
                    "error": str(exc)[:500],
                    "created_at": datetime.utcnow().isoformat() + "Z",
                },
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
