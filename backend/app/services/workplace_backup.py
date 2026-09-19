"""Versioned, company-isolated workplace backup production."""
from __future__ import annotations
import errno
import hashlib
import json, logging, os, shutil, tempfile, zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import entities
from app.models.entities import ArchiveKind, BackupSource, BackupStatus, Company, EisaArchiveRecord
from app.services.archive_store import _checksum, _maybe_encrypt_file, _rel_store, archive_root, resolve_archive_path, upload_root
from app.services.workplace_backup_report import build_workplace_backup_report


logger = logging.getLogger(__name__)

COMPANY_DOMAIN_MODELS = (
    ("branches", "Branch"), ("employees", "Employee"), ("personnel_profiles", "PersonnelProfile"),
    ("health_records", "HealthRecord"), ("risk_assessments", "RiskAssessment"), ("risk_revisions", "RiskRevision"),
    ("risk_media", "RiskMedia"), ("field_inspections", "FieldInspection"), ("ppe_assignments", "PpeAssignment"),
    ("ppe_inventory", "PpeInventoryItem"), ("chemical_products", "ChemicalProduct"), ("training_sessions", "TrainingSession"),
    ("documents", "DocumentRecord"), ("incidents", "IncidentEvent"), ("annual_plan_items", "AnnualPlanItem"),
    ("annual_evaluations", "AnnualPlanEvaluation"), ("committee_meetings", "OhsCommitteeMeeting"),
    ("committee_members", "OhsCommitteeMember"), ("drills", "DrillRecord"), ("emergency_plans", "EmergencyPlan"),
    ("emergency_teams", "EmergencyTeam"), ("work_permits", "WorkPermit"), ("contractors", "ContractorCompany"),
    ("visitor_passes", "VisitorPass"), ("periodic_controls", "PeriodicControl"),
    ("workplace_measurements", "WorkplaceMeasurement"), ("workplace_departments", "WorkplaceDepartment"),
    ("workplace_assignments", "WorkplaceAssignment"), ("service_contracts", "ServiceContract"),
)

@dataclass(frozen=True)
class PurgeSummary:
    deleted: int = 0
    failed: int = 0

@dataclass(frozen=True)
class BackupRunSummary:
    companies_seen: int = 0
    created: int = 0
    skipped: int = 0
    failed: int = 0
    purged: int = 0


BACKUP_MIN_FREE_BYTES = 128 * 1024 * 1024
BACKUP_ESTIMATE_OVERHEAD_BYTES = 64 * 1024 * 1024
STALE_BACKUP_ARTIFACT_AGE = timedelta(hours=1)
REMOTE_BACKUP_CHUNK_BYTES = 4 * 1024 * 1024


class BackupStorageFullError(RuntimeError):
    """Yedek üretimi için yerel disk alanı yetmediğinde kullanılır."""


class BackupIntegrityError(RuntimeError):
    """Uzak veya yerel yedek bütünlüğü doğrulanamadığında kullanılır."""


def _is_no_space_error(exc: BaseException) -> bool:
    return isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ENOSPC


def _company_file_bytes(company_id: int) -> int:
    root = upload_root() / str(company_id)
    if not root.exists():
        return 0
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += int(path.stat().st_size)
        except OSError:
            continue
    return total


def _backup_encryption_enabled() -> bool:
    from app.services.backup_restore import backup_encryption_key_material
    return bool(backup_encryption_key_material())


def _required_backup_free_bytes(company_id: int) -> int:
    source_bytes = _company_file_bytes(company_id)
    estimate = max(BACKUP_MIN_FREE_BYTES, source_bytes + BACKUP_ESTIMATE_OVERHEAD_BYTES)
    # Şifreleme sırasında geçici ZIP ve .enc dosyası kısa süre birlikte tutulur.
    return estimate * (2 if _backup_encryption_enabled() else 1)


def _ensure_backup_capacity(company_id: int) -> None:
    try:
        free_bytes = int(shutil.disk_usage(archive_root()).free)
    except OSError as exc:
        if _is_no_space_error(exc):
            raise BackupStorageFullError(
                "Yedek oluşturulamadı: depolama alanı dolu. Başarılı yedekler korunmuştur."
            ) from exc
        raise
    required_bytes = _required_backup_free_bytes(company_id)
    if free_bytes < required_bytes:
        free_mb = max(0, free_bytes // (1024 * 1024))
        required_mb = max(1, required_bytes // (1024 * 1024))
        raise BackupStorageFullError(
            "Yedek oluşturulamadı: depolama alanı yetersiz "
            f"(boş alan {free_mb} MB, tahmini ihtiyaç {required_mb} MB). "
            "Başarılı yedekler korunmuştur."
        )



def _remote_backup_store():
    """Return the configured R2/S3 store without making it a hard dependency."""
    if not bool(getattr(settings, "workplace_backup_remote_enabled", False)):
        return None
    try:
        from app.services.object_store import get_remote_object_store

        store = get_remote_object_store()
        if store is None:
            logger.warning(
                "İşyeri yedeği uzak depolama etkin fakat R2/S3 kimlik bilgileri hazır değil; "
                "yerel kopya korunuyor."
            )
        return store
    except Exception as exc:
        logger.warning(
            "İşyeri yedeği uzak depolama kullanılamadı; yerel kopya korunuyor: %s",
            type(exc).__name__,
        )
        return None


def _remote_backup_key(row: object) -> str:
    raw = str(getattr(row, "storage_path", "") or "").replace("\\", "/").strip("/")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise BackupIntegrityError("İşyeri yedeği için geçersiz depolama yolu.")
    prefix_raw = str(
        getattr(settings, "workplace_backup_remote_prefix", "workplace-backups") or ""
    ).replace("\\", "/").strip("/")
    prefix_parts = [part for part in prefix_raw.split("/") if part not in ("", ".")]
    if any(part == ".." for part in prefix_parts):
        raise BackupIntegrityError("İşyeri yedeği için geçersiz uzak depolama öneki.")
    normalized = "/".join(parts)
    prefix = "/".join(prefix_parts)
    return f"{prefix}/{normalized}" if prefix else normalized


def _local_workplace_backup_path(row: object) -> Path | None:
    raw = str(getattr(row, "storage_path", "") or "")
    if not raw:
        return None
    root = archive_root().resolve()
    candidate = (root / raw).resolve()
    if root not in candidate.parents:
        raise BackupIntegrityError("İşyeri yedeği arşiv yolu geçersiz.")
    return candidate if candidate.is_file() else None


def _remote_range_chunks(remote: object, key: str, *, start: int, end: int):
    iterator = getattr(remote, "iter_range", None)
    if callable(iterator):
        yield from iterator(key, start=start, end=end)
        return
    reader = getattr(remote, "get_range", None)
    if not callable(reader):
        raise BackupIntegrityError("Uzak depolama aralık okumasını desteklemiyor.")
    content = reader(key, start=start, end=end)
    if content:
        yield bytes(content)


def _remote_checksum(remote: object, key: str, size: int) -> str:
    expected_size = int(size)
    if expected_size < 0:
        raise BackupIntegrityError("Uzak yedek boyutu geçersiz.")
    digest = hashlib.sha256()
    received = 0
    start = 0
    while start < expected_size:
        end = min(expected_size - 1, start + REMOTE_BACKUP_CHUNK_BYTES - 1)
        for chunk in _remote_range_chunks(remote, key, start=start, end=end):
            payload = bytes(chunk)
            if not payload:
                continue
            received += len(payload)
            digest.update(payload)
        start = end + 1
    if received != expected_size:
        raise BackupIntegrityError(
            f"Uzak yedek boyutu doğrulanamadı: beklenen={expected_size}, gelen={received}"
        )
    return digest.hexdigest()


def _remote_archive_matches(
    remote: object,
    key: str,
    *,
    expected_size: int,
    expected_checksum: str | None,
) -> bool:
    size_reader = getattr(remote, "remote_size", None)
    if not callable(size_reader):
        raise BackupIntegrityError("Uzak depolama boyut doğrulamasını desteklemiyor.")
    remote_size = size_reader(key)
    if remote_size is None or int(remote_size) != int(expected_size):
        return False
    if not expected_checksum:
        return True
    return _remote_checksum(remote, key, int(remote_size)) == expected_checksum


def _upload_and_verify_remote_backup(
    remote: object,
    key: str,
    path: Path,
    *,
    expected_size: int,
    expected_checksum: str,
) -> None:
    if _remote_archive_matches(
        remote,
        key,
        expected_size=expected_size,
        expected_checksum=expected_checksum,
    ):
        return
    uploader = getattr(remote, "put_file", None)
    if not callable(uploader):
        raise BackupIntegrityError("Uzak depolama dosya yüklemeyi desteklemiyor.")
    uploader(key, path, content_type="application/octet-stream")
    size_reader = getattr(remote, "remote_size", None)
    remote_size = size_reader(key) if callable(size_reader) else None
    if remote_size is None or int(remote_size) != int(expected_size):
        raise BackupIntegrityError("Uzak yedek yüklemesi boyut doğrulamasından geçemedi.")
    remote_checksum = _remote_checksum(remote, key, int(remote_size))
    if remote_checksum != expected_checksum:
        try:
            remote.delete(key)
        except Exception:
            logger.warning("Bütünlüğü bozuk uzak yedek temizlenemedi: key=%s", key)
        raise BackupIntegrityError("Uzak yedek yüklemesi checksum doğrulamasından geçemedi.")


def _offload_completed_workplace_backup(
    row: object,
    *,
    local_path: Path | None = None,
    remote: object | None = None,
) -> bool:
    remote = remote or _remote_backup_store()
    if remote is None:
        return False
    path = local_path or _local_workplace_backup_path(row)
    if path is None or not path.is_file():
        return False
    local_size = int(path.stat().st_size)
    recorded_size = int(getattr(row, "size_bytes", 0) or 0)
    if recorded_size and recorded_size != local_size:
        raise BackupIntegrityError("Yerel yedek boyutu kayıtla uyuşmuyor.")
    local_checksum = _checksum(path)
    recorded_checksum = str(getattr(row, "checksum", "") or "")
    if recorded_checksum and recorded_checksum != local_checksum:
        raise BackupIntegrityError("Yerel yedek checksum doğrulamasından geçemedi.")
    expected_checksum = recorded_checksum or local_checksum
    key = _remote_backup_key(row)
    _upload_and_verify_remote_backup(
        remote,
        key,
        path,
        expected_size=local_size,
        expected_checksum=expected_checksum,
    )
    path.unlink()
    return True


def migrate_completed_workplace_backups(db: Session) -> dict[str, int]:
    """Move completed workplace backups to R2/S3 only after full verification."""
    remote = _remote_backup_store()
    summary = {"migrated": 0, "skipped": 0, "missing": 0, "failed": 0, "bytes_freed": 0}
    if remote is None:
        return summary
    rows = db.scalars(
        select(EisaArchiveRecord).where(
            EisaArchiveRecord.kind == ArchiveKind.TENANT_BACKUP,
            EisaArchiveRecord.entity_type == "workplace_backup_v4",
            EisaArchiveRecord.backup_status == BackupStatus.COMPLETED,
        )
    ).all()
    for row in rows:
        try:
            path = _local_workplace_backup_path(row)
            if path is None:
                size_reader = getattr(remote, "remote_size", None)
                remote_size = size_reader(_remote_backup_key(row)) if callable(size_reader) else None
                if remote_size is None:
                    summary["missing"] += 1
                    logger.error(
                        "Tamamlanmış işyeri yedeğinin yerel ve uzak kopyası yok: archive_id=%s",
                        row.id,
                    )
                else:
                    summary["skipped"] += 1
                continue
            size = int(path.stat().st_size)
            if _offload_completed_workplace_backup(row, local_path=path, remote=remote):
                summary["migrated"] += 1
                summary["bytes_freed"] += size
        except Exception as exc:
            summary["failed"] += 1
            logger.warning(
                "İşyeri yedeği uzak depolamaya taşınamadı; yerel kopya korundu: archive_id=%s error=%s",
                getattr(row, "id", "?"),
                type(exc).__name__,
            )
    return summary


def _maybe_reclaim_remote_backup_space(db: Session, company_id: int) -> dict[str, int]:
    if not bool(getattr(settings, "workplace_backup_remote_enabled", False)):
        return {}
    try:
        free_bytes = int(shutil.disk_usage(archive_root()).free)
        if free_bytes >= _required_backup_free_bytes(company_id):
            return {}
    except OSError:
        return {}
    summary = migrate_completed_workplace_backups(db)
    if summary.get("migrated"):
        logger.info(
            "İşyeri yedekleri R2/S3'e taşındı: adet=%s, boşaltılan_bytes=%s",
            summary["migrated"],
            summary["bytes_freed"],
        )
    return summary


def materialize_workplace_backup(row: object) -> tuple[Path, bool]:
    """Return a local path; download remote-only backups to a temporary file."""
    local = _local_workplace_backup_path(row)
    if local is not None:
        return local, False
    remote = _remote_backup_store()
    if remote is None:
        raise FileNotFoundError("İşyeri yedeği dosyası bulunamadı.")
    key = _remote_backup_key(row)
    size_reader = getattr(remote, "remote_size", None)
    remote_size = size_reader(key) if callable(size_reader) else None
    if remote_size is None:
        raise FileNotFoundError("İşyeri yedeği dosyası bulunamadı.")
    remote_size = int(remote_size)
    recorded_size = int(getattr(row, "size_bytes", 0) or 0)
    if recorded_size and recorded_size != remote_size:
        raise BackupIntegrityError("Uzak yedek boyutu kayıtla uyuşmuyor.")
    suffix = ".enc" if str(getattr(row, "storage_path", "")).endswith(".enc") else ".zip"
    fd, raw_path = tempfile.mkstemp(prefix="workplace-backup-", suffix=suffix)
    os.close(fd)
    path = Path(raw_path)
    try:
        with path.open("wb") as handle:
            start = 0
            while start < remote_size:
                end = min(remote_size - 1, start + REMOTE_BACKUP_CHUNK_BYTES - 1)
                for chunk in _remote_range_chunks(remote, key, start=start, end=end):
                    handle.write(bytes(chunk))
                start = end + 1
        if int(path.stat().st_size) != remote_size:
            raise BackupIntegrityError("Uzak yedek indirme boyutu doğrulanamadı.")
        recorded_checksum = str(getattr(row, "checksum", "") or "")
        if recorded_checksum and _checksum(path) != recorded_checksum:
            raise BackupIntegrityError("Uzak yedek checksum doğrulamasından geçemedi.")
        return path, True
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise

def _remove_stale_partial_files(*, stale_after: timedelta = STALE_BACKUP_ARTIFACT_AGE) -> int:
    root = archive_root() / "backups"
    if not root.exists():
        return 0
    cutoff = datetime.now().timestamp() - stale_after.total_seconds()
    deleted = 0
    for candidate in root.glob("company-*/.partial-*"):
        try:
            if candidate.is_file() and candidate.stat().st_mtime < cutoff:
                candidate.unlink()
                deleted += 1
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return deleted


def cleanup_incomplete_workplace_backups(
    db: Session,
    *,
    stale_after: timedelta = STALE_BACKUP_ARTIFACT_AGE,
) -> dict[str, int]:
    """Başarısız kayıtları ve eski geçici ZIP parçalarını temizler.

    COMPLETED kayıtlar ve onların dosyaları özellikle hiç dokunulmadan bırakılır.
    """
    deleted_partial_files = _remove_stale_partial_files(stale_after=stale_after)
    cutoff = datetime.utcnow() - stale_after
    rows = db.scalars(
        select(EisaArchiveRecord).where(
            EisaArchiveRecord.kind == ArchiveKind.TENANT_BACKUP,
            EisaArchiveRecord.entity_type == "workplace_backup_v4",
            EisaArchiveRecord.backup_status.in_(
                (BackupStatus.RUNNING, BackupStatus.FAILED)
            ),
            EisaArchiveRecord.created_at < cutoff,
        )
    ).all()
    for row in rows:
        db.delete(row)
    if rows:
        db.commit()
    return {
        "deleted_rows": len(rows),
        "deleted_partial_files": deleted_partial_files,
    }

def _json_value(value: Any) -> Any:
    if isinstance(value, Enum): return value.value
    if isinstance(value, (date, datetime)): return value.isoformat()
    if isinstance(value, bytes): return {"encoding": "hex", "value": value.hex()}
    return value

def _serialize_row(row: object) -> dict[str, Any]:
    return {column.key: _json_value(getattr(row, column.key)) for column in sa_inspect(type(row)).columns}

def _load_direct_company_domains(db: Session, company_id: int):
    payloads, unavailable = {}, {}
    for domain, model_name in COMPANY_DOMAIN_MODELS:
        model = getattr(entities, model_name, None)
        if model is None or not hasattr(model, "company_id"):
            unavailable[domain] = "not_available"; continue
        rows = db.scalars(select(model).where(model.company_id == company_id)).all()
        payloads[domain] = [_serialize_row(row) for row in rows]
    return payloads, unavailable

def _load_linked_domains(db: Session, company_id: int):
    ids = list(db.scalars(select(entities.TrainingSession.id).where(entities.TrainingSession.company_id == company_id)).all())
    rows = list(db.scalars(select(entities.TrainingParticipant).where(entities.TrainingParticipant.training_id.in_(ids))).all()) if ids else []
    return {"training_participants": [_serialize_row(row) for row in rows]}

def _write_company_files(zf: zipfile.ZipFile, company_id: int):
    root = upload_root() / str(company_id)
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file(): zf.write(path, f"files/{company_id}/{path.relative_to(root).as_posix()}")

def create_company_backup(db: Session, *, company_id: int, actor_user_id: int | None, source: BackupSource, schedule_key: str | None = None):
    company = db.scalar(select(Company).where(Company.id == company_id, Company.is_active.is_(True)))
    if company is None: raise ValueError("Aktif işyeri bulunamadı.")
    now = datetime.utcnow()
    row = EisaArchiveRecord(kind=ArchiveKind.TENANT_BACKUP, osgb_id=company.osgb_id, company_id=company.id,
        entity_type="workplace_backup_v4", entity_id=str(company.id), storage_path=f"pending/company-{company.id}/{uuid4().hex}",
        size_bytes=0, backup_source=source, backup_status=BackupStatus.RUNNING, started_at=now,
        schedule_key=schedule_key, created_by_user_id=actor_user_id)
    db.add(row); db.flush()
    folder = archive_root() / "backups" / f"company-{company.id}"
    base = f"workplace-{company.id}-{now:%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.zip"
    partial = folder / f".partial-{uuid4().hex}.zip"
    # Şifreleme başarısız olursa yarım .enc dosyasını da güvenle temizleyebilmek için
    # hedef yolu baştan biliyoruz.
    encrypted: Path | None = partial.with_suffix(partial.suffix + ".enc")
    try:
        _maybe_reclaim_remote_backup_space(db, company.id)
        folder.mkdir(parents=True, exist_ok=True)
        _remove_stale_partial_files()
        _ensure_backup_capacity(company.id)
        domains, unavailable = _load_direct_company_domains(db, company.id); domains.update(_load_linked_domains(db, company.id))
        counts = {name: len(items) for name, items in domains.items()}
        manifest = {"format_version": 4, "created_at": now.isoformat()+"Z", "backup_source": source.value,
            "osgb_id": company.osgb_id, "company_id": company.id, "companies": [{"id": company.id, "name": company.name}],
            "domain_counts": counts, "unavailable_domains": unavailable,
            "restore": {"supports_file_restore": True, "supports_db_row_restore": False}}
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
            for domain, items in domains.items(): zf.writestr(f"domains/{domain}.json", json.dumps(items, ensure_ascii=False, indent=2, default=str))
            zf.writestr("Yedek Raporu.html", build_workplace_backup_report(manifest, domains))
            _write_company_files(zf, company.id)
        encrypted = _maybe_encrypt_file(partial); final = folder / (base + (".enc" if encrypted.name.endswith(".enc") else "")); encrypted.replace(final)
        row.original_name = final.name; row.storage_path = _rel_store(final); row.size_bytes = final.stat().st_size
        row.checksum = _checksum(final); row.backup_status = BackupStatus.COMPLETED; row.completed_at = datetime.utcnow()
        row.notes = f"İşyeri yedeği v4 — {sum(counts.values())} kayıt, {len(domains)} alan"
        db.commit()
        db.refresh(row)
        try:
            _offload_completed_workplace_backup(row, local_path=final)
        except Exception as exc:
            logger.warning(
                "Yeni işyeri yedeği R2/S3'e taşınamadı; yerel kopya korundu: error=%s",
                type(exc).__name__,
            )
        return row
    except Exception as exc:
        for candidate in (partial, encrypted):
            if candidate is not None and candidate.exists():
                try:
                    candidate.unlink()
                except OSError:
                    pass
        storage_full = isinstance(exc, BackupStorageFullError) or _is_no_space_error(exc)
        message = (
            str(exc)
            if isinstance(exc, BackupStorageFullError)
            else (
                "Yedek oluşturulamadı: depolama alanı dolu. "
                "Başarılı yedekler korunmuştur."
                if storage_full
                else str(exc)[:1000]
            )
        )
        row.backup_status = BackupStatus.FAILED
        row.error_summary = message[:1000]
        row.completed_at = datetime.utcnow()
        db.commit()
        if storage_full and not isinstance(exc, BackupStorageFullError):
            raise BackupStorageFullError(message) from exc
        raise

def read_company_backup_manifest(row, path: Path | None = None):
    from app.services.backup_restore import _decrypt_if_needed

    cleanup_path = False
    if path is None:
        path, cleanup_path = materialize_workplace_backup(row)
    work = path
    try:
        work = _decrypt_if_needed(path)
        with zipfile.ZipFile(work) as zf:
            return json.loads(zf.read("manifest.json"))
    finally:
        if work != path and work.exists():
            work.unlink()
        if cleanup_path and path.exists():
            path.unlink()

def schedule_key(company_id: int, now: datetime) -> str:
    if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
    return f"company:{company_id}:daily:{now.astimezone(ZoneInfo('Europe/Istanbul')).date().isoformat()}"

def purge_expired_scheduled_backups(db: Session, *, cutoff: datetime):
    rows = db.scalars(select(EisaArchiveRecord).where(EisaArchiveRecord.kind == ArchiveKind.TENANT_BACKUP,
        EisaArchiveRecord.backup_source == BackupSource.SCHEDULED, EisaArchiveRecord.backup_status == BackupStatus.COMPLETED,
        EisaArchiveRecord.completed_at < cutoff)).all(); deleted = failed = 0
    remote = _remote_backup_store()
    for row in rows:
        try:
            path = _local_workplace_backup_path(row)
            remote_present = False
            if remote is not None:
                size_reader = getattr(remote, "remote_size", None)
                remote_size = size_reader(_remote_backup_key(row)) if callable(size_reader) else None
                remote_present = remote_size is not None
            if path is None and not remote_present:
                raise FileNotFoundError("Süreli işyeri yedeği bulunamadı.")
            if path is not None:
                path.unlink()
            if remote_present:
                remote.delete(_remote_backup_key(row))
            db.delete(row); db.commit(); deleted += 1
        except Exception:
            db.rollback(); failed += 1
    return PurgeSummary(deleted, failed)

def run_scheduled_company_backups(db_factory, *, now: datetime | None = None):
    now = now or datetime.utcnow()
    with db_factory() as db: ids = list(db.scalars(select(Company.id).where(Company.is_active.is_(True)).order_by(Company.id)).all())
    created = skipped = failed = 0
    cutoff = now - timedelta(days=max(1, settings.workplace_backup_retention_days))
    # Alan doluyken önce eski otomatik yedekleri sil; üretimden sonra temizlemek
    # disk doluluğu senaryosunda artık çok geç kalır.
    with db_factory() as db:
        purge_before = purge_expired_scheduled_backups(db, cutoff=cutoff)
    for company_id in ids:
        with db_factory() as db:
            key = schedule_key(company_id, now)
            if db.scalar(select(EisaArchiveRecord.id).where(EisaArchiveRecord.schedule_key == key)) is not None: skipped += 1; continue
            try: create_company_backup(db, company_id=company_id, actor_user_id=None, source=BackupSource.SCHEDULED, schedule_key=key); created += 1
            except Exception: db.rollback(); failed += 1
    with db_factory() as db:
        purge_after = purge_expired_scheduled_backups(db, cutoff=cutoff)
    return BackupRunSummary(
        len(ids),
        created,
        skipped,
        failed,
        purge_before.deleted + purge_after.deleted,
    )
