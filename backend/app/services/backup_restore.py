"""Yedek inceleme / geri yükleme iskeleti (P0-08).

- inspect: her zaman salt okunur (restore planı)
- restore_files: yalnızca backup_restore_enabled=True iken; DB satırı yazmaz
- Production'da varsayılan kapalı — canlı veri üzerine sessiz restore yok
"""
from __future__ import annotations

import json
import logging
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fastapi import HTTPException

from app.core.config import _INSECURE_SECRET_KEYS, settings
from app.services.archive_store import upload_root

logger = logging.getLogger(__name__)


def _probe_fernet_key(raw: str) -> bool:
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    f = Fernet(base64.urlsafe_b64encode(digest))
    token = f.encrypt(b"probe")
    return f.decrypt(token) == b"probe"


def _is_weak_key(raw: str) -> bool:
    return (
        len(raw) < 32
        or raw.lower() in _INSECURE_SECRET_KEYS
        or raw.startswith("change-me")
    )


def backup_encryption_key_material() -> str:
    """Dedicated key veya (production cutover) SECRET_KEY türevi."""
    dedicated = (settings.backup_encryption_key or "").strip()
    if dedicated:
        return dedicated
    if bool(getattr(settings, "backup_encryption_force_off", False)):
        return ""
    if bool(getattr(settings, "backup_encryption_secret_fallback", False)):
        return (settings.secret_key or "").strip()
    return ""


def backup_encryption_key_status() -> str:
    """dedicated | secret_key_fallback | weak | weak_fallback | missing | invalid"""
    dedicated = (settings.backup_encryption_key or "").strip()
    if dedicated:
        try:
            if not _probe_fernet_key(dedicated):
                return "invalid"
        except Exception:
            return "invalid"
        return "weak" if _is_weak_key(dedicated) else "dedicated"
    if bool(getattr(settings, "backup_encryption_force_off", False)):
        return "missing"
    if not bool(getattr(settings, "backup_encryption_secret_fallback", False)):
        return "missing"
    secret = (settings.secret_key or "").strip()
    if not secret:
        return "missing"
    try:
        if not _probe_fernet_key(secret):
            return "invalid"
    except Exception:
        return "invalid"
    return "weak_fallback" if _is_weak_key(secret) else "secret_key_fallback"


def backup_encryption_readiness() -> dict:
    status = backup_encryption_key_status()
    return {
        "restore_enabled": bool(settings.backup_restore_enabled),
        "key_status": status,
        "can_encrypt": status in ("dedicated", "secret_key_fallback"),
        "probe_ok": status in ("dedicated", "secret_key_fallback", "weak", "weak_fallback"),
    }


def backup_crypto_ready_label() -> str:
    ready = backup_encryption_readiness()
    if ready["can_encrypt"]:
        return "ok"
    return "not_ready"


def enable_backup_crypto_for_production() -> str:
    """Production: dedicated yoksa güçlü SECRET_KEY ile yedek şifrelemesini aç."""
    env = (settings.environment or "").strip().lower()
    if env not in ("production", "prod", "live"):
        return "skipped-non-prod"
    if bool(getattr(settings, "backup_encryption_force_off", False)):
        settings.backup_encryption_secret_fallback = False
        return "force-off"
    dedicated = (settings.backup_encryption_key or "").strip()
    if dedicated:
        status = backup_encryption_key_status()
        if status == "dedicated":
            logger.info("backup encryption already dedicated")
            return f"already:{status}"
        logger.warning("backup encryption dedicated key not usable (%s)", status)
        return f"not-ready:{status}"
    settings.backup_encryption_secret_fallback = True
    status = backup_encryption_key_status()
    if status == "secret_key_fallback":
        logger.info("backup encryption enabled (%s)", status)
        return f"enabled:{status}"
    settings.backup_encryption_secret_fallback = False
    logger.warning("backup encryption not ready (%s)", status)
    return f"not-ready:{status}"


@dataclass
class RestorePlan:
    archive_name: str
    format_version: int | None
    created_at: str | None
    osgb_id: int | None
    osgb_name: str | None
    companies: list[dict] = field(default_factory=list)
    document_count: int = 0
    employee_count: int = 0
    domain_counts: dict = field(default_factory=dict)
    file_entries: list[str] = field(default_factory=list)
    encrypted: bool = False
    restore_enabled: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _backup_decrypt_key_candidates() -> list[str]:
    """Dedicated + material + SECRET_KEY (eski fallback .enc için)."""
    out: list[str] = []
    for raw in (
        (settings.backup_encryption_key or "").strip(),
        backup_encryption_key_material(),
        (settings.secret_key or "").strip(),
    ):
        if raw and raw not in out:
            out.append(raw)
    return out


def _decrypt_if_needed(path: Path) -> Path:
    """`.enc` ise geçici düz dosya üretir (çağıran silmeli); değilse path döner."""
    if not path.name.endswith(".enc"):
        return path
    candidates = _backup_decrypt_key_candidates()
    if not candidates:
        raise HTTPException(
            status_code=400,
            detail="Şifreli yedek; BACKUP_ENCRYPTION_KEY / SECRET_KEY türevi yok.",
        )
    import base64
    import hashlib
    import tempfile

    from cryptography.fernet import Fernet, InvalidToken

    cipher = path.read_bytes()
    plain: bytes | None = None
    last_exc: Exception | None = None
    for key in candidates:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        f = Fernet(base64.urlsafe_b64encode(digest))
        try:
            plain = f.decrypt(cipher)
            break
        except InvalidToken as exc:
            last_exc = exc
            continue
    if plain is None:
        raise HTTPException(status_code=400, detail="Yedek çözülemedi (anahtar uyuşmuyor).") from last_exc
    tmp = Path(tempfile.mkstemp(suffix=".zip")[1])
    tmp.write_bytes(plain)
    return tmp


def inspect_backup_file(path: Path, *, archive_name: str | None = None) -> RestorePlan:
    encrypted = path.name.endswith(".enc")
    work = _decrypt_if_needed(path)
    cleanup = work != path
    try:
        if not zipfile.is_zipfile(work):
            raise HTTPException(status_code=400, detail="Yedek ZIP değil veya bozuk.")
        with zipfile.ZipFile(work, "r") as zf:
            names = zf.namelist()
            manifest: dict = {}
            if "manifest.json" in names:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            docs = []
            emps = []
            if "documents.json" in names:
                docs = json.loads(zf.read("documents.json").decode("utf-8"))
            if "employees.json" in names:
                emps = json.loads(zf.read("employees.json").decode("utf-8"))
            domain_counts = dict(manifest.get("domain_counts") or {})
            for key, fname in (
                ("health_records", "health_records.json"),
                ("risk_assessments", "risk_assessments.json"),
                ("incident_events", "incident_events.json"),
                ("workplace_assignments", "workplace_assignments.json"),
                ("service_contracts", "service_contracts.json"),
            ):
                if key not in domain_counts and fname in names:
                    try:
                        payload = json.loads(zf.read(fname).decode("utf-8"))
                        domain_counts[key] = len(payload) if isinstance(payload, list) else 0
                    except Exception:
                        domain_counts[key] = 0
            if "training_sessions" not in domain_counts and "trainings.json" in names:
                try:
                    payload = json.loads(zf.read("trainings.json").decode("utf-8"))
                    if isinstance(payload, dict):
                        domain_counts["training_sessions"] = len(payload.get("sessions") or [])
                        domain_counts["training_participants"] = len(payload.get("participants") or [])
                except Exception:
                    pass
            files = sorted(
                n for n in names if n.startswith("files/") or n.startswith("osgb_files/")
            )
            notes = [
                "Bu plan salt okunurdur; otomatik geri yükleme yapmaz.",
                "Dry-run dosya eşlemesi her zaman açık; diske yazma BACKUP_RESTORE_ENABLED=true + confirm=RESTORE ister.",
                "Veritabanı satır restore bu sürümde yoktur (güvenlik); domain JSON export salt okunur.",
                "osgb_files/* → {osgb_id}/* (manifest).",
            ]
            if encrypted:
                notes.append("Yedek şifreli (.enc); inceleme için sunucu anahtarı kullanıldı.")
            if (manifest.get("format_version") or 0) >= 3:
                notes.append("format_version>=3: sağlık/risk/eğitim/görevlendirme/olay JSON dahil.")
            return RestorePlan(
                archive_name=archive_name or path.name,
                format_version=manifest.get("format_version"),
                created_at=manifest.get("created_at"),
                osgb_id=manifest.get("osgb_id"),
                osgb_name=manifest.get("osgb_name"),
                companies=list(manifest.get("companies") or []),
                document_count=len(docs) if isinstance(docs, list) else 0,
                employee_count=len(emps) if isinstance(emps, list) else 0,
                domain_counts=domain_counts,
                file_entries=files[:200],
                encrypted=encrypted,
                restore_enabled=bool(settings.backup_restore_enabled),
                notes=notes,
            )
    finally:
        if cleanup:
            try:
                work.unlink(missing_ok=True)
            except OSError:
                pass


def restore_files_from_backup(
    path: Path,
    *,
    dry_run: bool = True,
    confirm: str | None = None,
) -> dict:
    """Zip içindeki files/ ve osgb_files/ girdilerini upload_dir altına yazar.

    dry_run=True: yalnızca eşleme/sayım (flag gerekmez).
    Gerçek yazma: backup_restore_enabled + confirm=RESTORE.
    """
    if not dry_run and not settings.backup_restore_enabled:
        raise HTTPException(
            status_code=403,
            detail="Geri yükleme yazımı kapalı (BACKUP_RESTORE_ENABLED). Dry-run kullanın.",
        )
    if not dry_run and (confirm or "").strip() != "RESTORE":
        raise HTTPException(status_code=422, detail='Onay için confirm="RESTORE" gerekli.')

    env = (settings.environment or "").strip().lower()
    if not dry_run and env in ("production", "prod", "live"):
        # Prod'da bile flag açık olsa ek uyarı — yine de izin ver (ops bilinçli açtı)
        pass

    work = _decrypt_if_needed(path)
    cleanup = work != path
    written: list[str] = []
    skipped: list[str] = []
    try:
        root = upload_root()
        with zipfile.ZipFile(work, "r") as zf:
            names = zf.namelist()
            manifest: dict = {}
            if "manifest.json" in names:
                try:
                    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    manifest = {}
            osgb_id_raw = manifest.get("osgb_id")
            try:
                osgb_id = int(osgb_id_raw) if osgb_id_raw is not None else None
            except (TypeError, ValueError):
                osgb_id = None

            for name in names:
                if name.endswith("/"):
                    continue
                rel: str | None = None
                if name.startswith("files/"):
                    rel = name[len("files/") :]
                elif name.startswith("osgb_files/"):
                    rest = name[len("osgb_files/") :]
                    if osgb_id is None:
                        skipped.append(name)
                        continue
                    rel = f"{osgb_id}/{rest}" if rest else None
                else:
                    continue
                if not rel or ".." in Path(rel).parts:
                    skipped.append(name)
                    continue
                target = (root / rel).resolve()
                if root not in target.parents and target != root:
                    skipped.append(name)
                    continue
                if dry_run:
                    written.append(rel)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(name))
                written.append(rel)
        return {
            "dry_run": dry_run,
            "files_touched": len(written),
            "sample": written[:50],
            "skipped": skipped[:50],
            "message": (
                "Dry-run: yazılacak dosya listesi."
                if dry_run
                else f"{len(written)} dosya geri yüklendi."
            ),
        }
    finally:
        if cleanup:
            try:
                work.unlink(missing_ok=True)
            except OSError:
                pass
