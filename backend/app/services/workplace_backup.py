"""Versioned, company-isolated workplace backup production."""
from __future__ import annotations
import errno
import json, shutil, zipfile
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


class BackupStorageFullError(RuntimeError):
    """Yedek üretimi için yerel disk alanı yetmediğinde kullanılır."""


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
        row.notes = f"İşyeri yedeği v4 — {sum(counts.values())} kayıt, {len(domains)} alan"; db.commit(); db.refresh(row); return row
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

def read_company_backup_manifest(row):
    from app.services.backup_restore import _decrypt_if_needed
    path = resolve_archive_path(row); work = _decrypt_if_needed(path)
    try:
        with zipfile.ZipFile(work) as zf: return json.loads(zf.read("manifest.json"))
    finally:
        if work != path and work.exists(): work.unlink()

def schedule_key(company_id: int, now: datetime) -> str:
    if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
    return f"company:{company_id}:daily:{now.astimezone(ZoneInfo('Europe/Istanbul')).date().isoformat()}"

def purge_expired_scheduled_backups(db: Session, *, cutoff: datetime):
    rows = db.scalars(select(EisaArchiveRecord).where(EisaArchiveRecord.kind == ArchiveKind.TENANT_BACKUP,
        EisaArchiveRecord.backup_source == BackupSource.SCHEDULED, EisaArchiveRecord.backup_status == BackupStatus.COMPLETED,
        EisaArchiveRecord.completed_at < cutoff)).all(); deleted = failed = 0
    for row in rows:
        try:
            path = resolve_archive_path(row)
            if path.exists(): path.unlink()
            db.delete(row); db.commit(); deleted += 1
        except OSError: db.rollback(); failed += 1
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
