"""Yedek inceleme / geri yükleme iskeleti (P0-08).

- inspect: her zaman salt okunur (restore planı)
- restore_files: yalnızca backup_restore_enabled=True iken; DB satırı yazmaz
- Production'da varsayılan kapalı — canlı veri üzerine sessiz restore yok
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings
from app.services.archive_store import upload_root


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
    file_entries: list[str] = field(default_factory=list)
    encrypted: bool = False
    restore_enabled: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _decrypt_if_needed(path: Path) -> Path:
    """`.enc` ise geçici düz dosya üretir (çağıran silmeli); değilse path döner."""
    if not path.name.endswith(".enc"):
        return path
    key = (settings.backup_encryption_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=400,
            detail="Şifreli yedek; BACKUP_ENCRYPTION_KEY tanımlı değil.",
        )
    import base64
    import hashlib
    import tempfile

    from cryptography.fernet import Fernet, InvalidToken

    digest = hashlib.sha256(key.encode("utf-8")).digest()
    f = Fernet(base64.urlsafe_b64encode(digest))
    try:
        plain = f.decrypt(path.read_bytes())
    except InvalidToken as exc:
        raise HTTPException(status_code=400, detail="Yedek çözülemedi (anahtar uyuşmuyor).") from exc
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
            files = sorted(
                n for n in names if n.startswith("files/") or n.startswith("osgb_files/")
            )
            notes = [
                "Bu plan salt okunurdur; otomatik geri yükleme yapmaz.",
                "Dosya geri yükleme BACKUP_RESTORE_ENABLED=true olmadan çalışmaz.",
                "Veritabanı satır restore bu sürümde yoktur (güvenlik).",
            ]
            if encrypted:
                notes.append("Yedek şifreli (.enc); inceleme için sunucu anahtarı kullanıldı.")
            return RestorePlan(
                archive_name=archive_name or path.name,
                format_version=manifest.get("format_version"),
                created_at=manifest.get("created_at"),
                osgb_id=manifest.get("osgb_id"),
                osgb_name=manifest.get("osgb_name"),
                companies=list(manifest.get("companies") or []),
                document_count=len(docs) if isinstance(docs, list) else 0,
                employee_count=len(emps) if isinstance(emps, list) else 0,
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

    dry_run=True: yalnızca sayım. Gerçek yazma: flag + confirm=RESTORE.
    """
    if not settings.backup_restore_enabled:
        raise HTTPException(
            status_code=403,
            detail="Geri yükleme kapalı (BACKUP_RESTORE_ENABLED). Önce restore-plan kullanın.",
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
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                rel: str | None = None
                if name.startswith("files/"):
                    rel = name[len("files/") :]
                elif name.startswith("osgb_files/"):
                    # osgb_files/visits/x → {osgb}/visits/x — manifest osgb_id gerekir
                    # Güvenli yol: yalnızca relative parçayı jail içinde tut
                    rel = name[len("osgb_files/") :]
                    # Eski yedek düzeni: uploads/{osgb_id}/visits/... — çağıran bilmeli;
                    # burada osgb_files altında olduğu gibi yazamayız. manifest'ten al.
                    continue  # osgb dosyaları ayrı PR; company files önce
                else:
                    continue
                if not rel or ".." in rel.split("/"):
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
