"""Versioned, company-isolated workplace backup production."""
from __future__ import annotations
import json, zipfile
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
    folder = archive_root() / "backups" / f"company-{company.id}"; folder.mkdir(parents=True, exist_ok=True)
    base = f"workplace-{company.id}-{now:%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.zip"
    partial = folder / f".partial-{uuid4().hex}.zip"; encrypted: Path | None = None
    try:
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
            if candidate is not None and candidate.exists(): candidate.unlink()
        row.backup_status = BackupStatus.FAILED; row.error_summary = str(exc)[:1000]; row.completed_at = datetime.utcnow(); db.commit(); raise

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
    for company_id in ids:
        with db_factory() as db:
            key = schedule_key(company_id, now)
            if db.scalar(select(EisaArchiveRecord.id).where(EisaArchiveRecord.schedule_key == key)) is not None: skipped += 1; continue
            try: create_company_backup(db, company_id=company_id, actor_user_id=None, source=BackupSource.SCHEDULED, schedule_key=key); created += 1
            except Exception: db.rollback(); failed += 1
    with db_factory() as db: purge = purge_expired_scheduled_backups(db, cutoff=now-timedelta(days=max(1, settings.workplace_backup_retention_days)))
    return BackupRunSummary(len(ids), created, skipped, failed, purge.deleted)
