"""Yedek yönetimi — offsite (R2/S3) kopya, saklama politikası ve RPO izleme.

İBYS Yedekleme Prosedürü gereksinimleri:

- 3-2-1: Yedekler yalnızca veritabanıyla aynı hesapta kalmamalı; doğrulanmış
  bir offsite kopya (R2/S3) tutulur.
- Saklama: günlük 30 gün, haftalık 12 hafta, aylık 12 ay (GFS).
- RPO izleme: son başarılı yedeğin yaşı ``BACKUP_MAX_AGE_HOURS`` sınırını
  aşarsa sistem sağlığı degraded olur.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


# isgsuite-20260921-030000.dump / .db / .dump.enc
_DB_BACKUP_NAME = re.compile(r"^isgsuite-(\d{8})-(\d{6})\.(dump|db)(\.enc)?$")
# Dış modüller (scriptler) için genel ad.
DB_BACKUP_NAME = _DB_BACKUP_NAME


class BackupOffsiteError(RuntimeError):
    """Offsite yedek yüklemesi doğrulanamadığında kullanılır."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def offsite_store():
    """``BACKUP_REMOTE_ENABLED`` açıkken uzak depoyu döndürür, aksi halde None."""
    if not bool(getattr(settings, "backup_remote_enabled", False)):
        return None
    try:
        from app.services.object_store import get_remote_object_store

        store = get_remote_object_store()
    except Exception as exc:  # pragma: no cover - savunmacı
        logger.error("Offsite yedek deposu başlatılamadı: %s", type(exc).__name__)
        return None
    if store is None:
        logger.error(
            "Offsite yedek açık fakat R2/S3 kimlik bilgileri hazır değil; "
            "yerel kopya korunuyor."
        )
    return store


def notify_global_admins(
    *,
    title: str,
    message: str,
    entity_type: str,
    entity_id: str | None = None,
) -> int:
    """Global yöneticilere kritik bildirim üretir (en iyi çaba).

    Yedek altyapısı bozulduğunda alarmın sessiz kalmaması içindir. Hiçbir
    durumda çağıran akışı bozmaz; hata hâlinde 0 döner.
    """
    try:
        from sqlalchemy import select

        from app.core.database import SessionLocal
        from app.models.entities import Notification, NotificationType, User, UserRole

        with SessionLocal() as db:
            admins = list(
                db.scalars(
                    select(User).where(
                        User.role == UserRole.GLOBAL_ADMIN,
                        User.is_active.is_(True),
                    )
                ).all()
            )
            for admin in admins:
                db.add(
                    Notification(
                        user_id=admin.id,
                        company_id=None,
                        type=NotificationType.CRITICAL,
                        title=title[:220],
                        message=message[:1200],
                        entity_type=entity_type,
                        entity_id=entity_id,
                    )
                )
            db.commit()
            return len(admins)
    except Exception:  # pragma: no cover - alarm asla akışı bozmaz
        logger.exception("Yedek alarmı gönderilemedi")
        return 0


def offsite_key(local_path: Path, *, prefix: str | None = None) -> str:
    """Offsite nesne anahtarı — yol geçişi (traversal) reddedilir."""
    raw_prefix = str(
        prefix
        if prefix is not None
        else getattr(settings, "backup_remote_prefix", "db-backups")
    )
    parts = [part for part in raw_prefix.replace("\\", "/").split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise BackupOffsiteError("Geçersiz offsite yedek öneki.")
    name = Path(local_path).name
    if not name or name in (".", ".."):
        raise BackupOffsiteError("Geçersiz offsite yedek dosya adı.")
    return "/".join(parts + [name]) if parts else name


def upload_backup_to_offsite(
    path: Path,
    *,
    key: str | None = None,
    store=None,
) -> dict:
    """Yedeği R2/S3'e yükler ve boyut + SHA-256 ile doğrular.

    Doğrulama başarısızsa uzak nesne silinir ve ``BackupOffsiteError`` yükseltilir;
    yerel dosya asla silinmez.
    """
    source = Path(path)
    if not source.is_file():
        raise BackupOffsiteError("Offsite yükleme için yerel yedek bulunamadı.")

    remote = store or offsite_store()
    if remote is None:
        return {"uploaded": False, "reason": "remote-disabled"}

    target_key = key or offsite_key(source)
    expected_size = int(source.stat().st_size)
    expected_checksum = _sha256(source)

    uploader = getattr(remote, "put_file", None)
    if not callable(uploader):
        raise BackupOffsiteError("Uzak depolama dosya yüklemeyi desteklemiyor.")

    uploader(target_key, source, content_type="application/octet-stream")

    size_reader = getattr(remote, "remote_size", None)
    remote_size = size_reader(target_key) if callable(size_reader) else None
    if remote_size is None or int(remote_size) != expected_size:
        _delete_best_effort(remote, target_key)
        raise BackupOffsiteError(
            "Offsite yedek boyut doğrulamasından geçemedi "
            f"(beklenen={expected_size}, gelen={remote_size})."
        )

    remote_checksum = _remote_checksum(remote, target_key, expected_size)
    if remote_checksum != expected_checksum:
        _delete_best_effort(remote, target_key)
        raise BackupOffsiteError("Offsite yedek checksum doğrulamasından geçemedi.")

    return {
        "uploaded": True,
        "key": target_key,
        "size_bytes": expected_size,
        "checksum": expected_checksum,
    }


def _delete_best_effort(remote, key: str) -> None:
    deleter = getattr(remote, "delete", None)
    if not callable(deleter):
        return
    try:
        deleter(key)
    except Exception:  # pragma: no cover - en iyi çaba
        logger.warning("Bütünlüğü bozuk offsite yedek temizlenemedi: key=%s", key)


def _remote_checksum(remote, key: str, size: int) -> str:
    digest = hashlib.sha256()
    received = 0
    chunk_bytes = 4 * 1024 * 1024
    iterator = getattr(remote, "iter_range", None)
    if not callable(iterator):
        raise BackupOffsiteError("Uzak depolama aralık okumasını desteklemiyor.")
    start = 0
    while start < size:
        end = min(size - 1, start + chunk_bytes - 1)
        for chunk in iterator(key, start=start, end=end):
            payload = bytes(chunk)
            if not payload:
                continue
            received += len(payload)
            digest.update(payload)
        start = end + 1
    if received != size:
        raise BackupOffsiteError(
            f"Offsite yedek boyutu doğrulanamadı: beklenen={size}, gelen={received}"
        )
    return digest.hexdigest()


@dataclass(frozen=True)
class RetentionSummary:
    kept: int = 0
    deleted: int = 0
    failed: int = 0
    deleted_files: list[str] = field(default_factory=list)


def _classify_database_backups(paths: list[Path], *, now: datetime) -> tuple[set[Path], set[Path]]:
    """GFS sınıflandırması: saklanacaklar ve silinecekler.

    Katmanlar yaşa göre ayrıktır:
    - günlük pencere (``DB_BACKUP_RETENTION_DAYS``): hepsi saklanır
    - haftalık pencere: her ISO haftasının en yeni yedeği saklanır
    - aylık pencere: her ayın en yeni yedeği saklanır
    - daha eskisi silinir
    """
    dated: list[tuple[datetime, Path]] = []
    undated: list[Path] = []
    for path in paths:
        match = _DB_BACKUP_NAME.match(path.name)
        if not match:
            undated.append(path)
            continue
        try:
            stamp = datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M%S")
        except ValueError:
            undated.append(path)
            continue
        dated.append((stamp, path))
    dated.sort(key=lambda item: item[0], reverse=True)

    keep: set[Path] = set(undated)
    delete: set[Path] = set()

    daily_cutoff = now - timedelta(days=max(1, int(settings.db_backup_retention_days)))
    weekly_cutoff = now - timedelta(weeks=max(1, int(settings.db_backup_weekly_retention_weeks)))
    monthly_cutoff = now - timedelta(days=31 * max(1, int(settings.db_backup_monthly_retention_months)))

    weekly_seen: set[tuple[int, int]] = set()
    monthly_seen: set[tuple[int, int]] = set()

    for stamp, path in dated:
        iso = stamp.isocalendar()
        week_key = (iso[0], iso[1])
        month_key = (stamp.year, stamp.month)

        if stamp >= daily_cutoff:
            keep.add(path)
        elif stamp >= weekly_cutoff:
            if week_key in weekly_seen:
                delete.add(path)
            else:
                weekly_seen.add(week_key)
                keep.add(path)
        elif stamp >= monthly_cutoff:
            if month_key in monthly_seen:
                delete.add(path)
            else:
                monthly_seen.add(month_key)
                keep.add(path)
        else:
            delete.add(path)

    return keep, delete


def purge_expired_database_backups(*, now: datetime | None = None, directory: Path | None = None) -> RetentionSummary:
    """``BACKUP_DIR`` içindeki süresi dolmuş DB dump'larını GFS ile temizler."""
    now = now or datetime.utcnow()
    root = Path(directory or settings.backup_dir).resolve()
    if not root.exists():
        return RetentionSummary()

    candidates = [p for p in root.iterdir() if p.is_file() and _DB_BACKUP_NAME.match(p.name)]
    if not candidates:
        return RetentionSummary()

    keep, delete = _classify_database_backups(candidates, now=now)
    remote = offsite_store()
    deleted_files: list[str] = []
    failed = 0
    for path in sorted(delete):
        try:
            path.unlink()
            deleted_files.append(path.name)
        except OSError:
            failed += 1
            continue
        if remote is not None:
            try:
                remote.delete(offsite_key(path))
            except Exception:  # pragma: no cover - en iyi çaba
                logger.warning("Offsite süresi dolmuş yedek silinemedi: %s", path.name)

    return RetentionSummary(
        kept=len(keep),
        deleted=len(deleted_files),
        failed=failed,
        deleted_files=deleted_files,
    )


def database_backup_status(*, now: datetime | None = None, directory: Path | None = None) -> dict:
    """RPO izleme — son başarılı DB yedeğinin yaşı ve saklama özeti."""
    now = now or datetime.utcnow()
    root = Path(directory or settings.backup_dir).resolve()
    latest: datetime | None = None
    count = 0
    if root.exists():
        for path in root.iterdir():
            if not path.is_file():
                continue
            match = _DB_BACKUP_NAME.match(path.name)
            if not match:
                continue
            count += 1
            try:
                stamp = datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M%S")
            except ValueError:
                continue
            if latest is None or stamp > latest:
                latest = stamp

    max_age_hours = max(1, int(getattr(settings, "backup_max_age_hours", 36)))
    age_hours: float | None = None
    if latest is not None:
        age_hours = round((now - latest).total_seconds() / 3600.0, 2)
    healthy = latest is not None and age_hours is not None and age_hours <= max_age_hours
    return {
        "enabled": bool(getattr(settings, "db_backup_enabled", True)),
        "offsite_enabled": bool(getattr(settings, "backup_remote_enabled", False)),
        "offsite_required": bool(getattr(settings, "backup_remote_required", False)),
        "backup_count": count,
        "latest_backup_at": latest.isoformat() + "Z" if latest else None,
        "age_hours": age_hours,
        "max_age_hours": max_age_hours,
        "healthy": healthy,
        "retention_days": int(getattr(settings, "db_backup_retention_days", 30)),
    }
