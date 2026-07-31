"""Merkezi tarihli arşiv — tenant yedekleri + silinen dosya kopyaları."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    ArchiveKind,
    Company,
    DocumentRecord,
    EisaArchiveRecord,
    Employee,
    HealthRecord,
    IncidentEvent,
    OsgbOrganization,
    RiskAssessment,
    ServiceContract,
    TrainingParticipant,
    TrainingSession,
    User,
    WorkplaceAssignment,
)


def archive_root() -> Path:
    root = Path(settings.backup_dir).resolve() / "central_archive"
    root.mkdir(parents=True, exist_ok=True)
    return root


def upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel_store(path: Path) -> str:
    return str(path.relative_to(archive_root())).replace("\\", "/")


def _maybe_encrypt_file(path: Path) -> Path:
    """Anahtar varsa Fernet ile .enc üretir; düz zip'i siler."""
    from app.services.backup_restore import backup_encryption_key_material

    key = backup_encryption_key_material()
    if not key:
        return path
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    digest = hashlib.sha256(key.encode("utf-8")).digest()
    f = Fernet(base64.urlsafe_b64encode(digest))
    enc_path = path.with_suffix(path.suffix + ".enc")
    enc_path.write_bytes(f.encrypt(path.read_bytes()))
    try:
        path.unlink()
    except OSError:
        pass
    return enc_path


def archive_file_before_delete(
    db: Session,
    *,
    source: Path,
    user: User | None,
    company_id: int | None,
    osgb_id: int | None = None,
    entity_type: str,
    entity_id: str | None,
    original_name: str | None = None,
    notes: str | None = None,
) -> EisaArchiveRecord | None:
    """Silmeden önce dosyayı merkezi arşive kopyala. Kaynak yoksa None."""
    try:
        src = source.resolve()
    except OSError:
        return None
    if not src.exists() or not src.is_file():
        return None

    if company_id and not osgb_id:
        company = db.get(Company, company_id)
        osgb_id = company.osgb_id if company else None

    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    folder = archive_root() / "deleted" / f"osgb-{osgb_id or 0}" / f"company-{company_id or 0}" / stamp
    folder.mkdir(parents=True, exist_ok=True)
    dest_name = f"{entity_type}-{entity_id or 'x'}-{uuid4().hex[:10]}{src.suffix}"
    dest = folder / dest_name
    shutil.copy2(src, dest)

    row = EisaArchiveRecord(
        kind=ArchiveKind.DELETED_FILE,
        osgb_id=osgb_id,
        company_id=company_id,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        original_name=original_name or src.name,
        storage_path=_rel_store(dest),
        size_bytes=dest.stat().st_size,
        checksum=_checksum(dest),
        notes=notes or "Silme öncesi otomatik arşiv",
        created_by_user_id=user.id if user else None,
    )
    db.add(row)
    db.flush()
    return row


def _enum_val(v):
    return v.value if hasattr(v, "value") else v


def _dt(v):
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _json_bytes(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _serialize_health(rows: list[HealthRecord]) -> list[dict]:
    """Ciphertext olduğu gibi yedeklenir (düz metne çözülmez)."""
    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "company_id": r.company_id,
                "employee_id": r.employee_id,
                "record_type": _enum_val(r.record_type),
                "examination_date": _dt(r.examination_date),
                "next_examination_date": _dt(r.next_examination_date),
                "fitness_status": _enum_val(r.fitness_status),
                "physician_name": r.physician_name,
                "summary": r.summary,
                "confidential_note": r.confidential_note,
                "audiometry_date": _dt(r.audiometry_date),
                "audiometry_result": r.audiometry_result,
                "spirometry_date": _dt(r.spirometry_date),
                "spirometry_result": r.spirometry_result,
                "chest_xray_date": _dt(r.chest_xray_date),
                "chest_xray_result": r.chest_xray_result,
                "blood_lead_date": _dt(r.blood_lead_date),
                "blood_lead_value": r.blood_lead_value,
                "blood_lead_unit": r.blood_lead_unit,
                "blood_lead_ref": r.blood_lead_ref,
                "blood_lead_eval": r.blood_lead_eval,
                "suggested_tests": r.suggested_tests,
                "exposures": r.exposures,
                "follow_up_note": r.follow_up_note,
                "other_biological_test": r.other_biological_test,
                "report_file_name": r.report_file_name,
                "report_storage_path": r.report_storage_path,
                "deleted_at": _dt(r.deleted_at),
                "created_at": _dt(r.created_at),
            }
        )
    return out


def _serialize_risks(rows: list[RiskAssessment]) -> list[dict]:
    return [
        {
            "id": r.id,
            "risk_code": r.risk_code,
            "company_id": r.company_id,
            "hazard_id": r.hazard_id,
            "department_name": r.department_name,
            "activity": r.activity,
            "risk_definition": r.risk_definition,
            "probability": r.probability,
            "severity": r.severity,
            "risk_score": r.risk_score,
            "risk_level": r.risk_level,
            "status": r.status,
            "term_date": _dt(r.term_date),
            "created_at": _dt(r.created_at),
        }
        for r in rows
    ]


def _serialize_trainings(sessions: list[TrainingSession], participants: list[TrainingParticipant]) -> dict:
    return {
        "sessions": [
            {
                "id": t.id,
                "company_id": t.company_id,
                "title": t.title,
                "training_type": t.training_type,
                "start_date": _dt(t.start_date),
                "end_date": _dt(t.end_date),
                "duration_hours": t.duration_hours,
                "instructor_name": t.instructor_name,
                "status": _enum_val(t.status),
                "verification_code": t.verification_code,
                "created_at": _dt(t.created_at),
            }
            for t in sessions
        ],
        "participants": [
            {
                "id": p.id,
                "training_id": p.training_id,
                "employee_id": p.employee_id,
                "attended": p.attended,
                "score": p.score,
                "successful": p.successful,
                "certificate_number": p.certificate_number,
            }
            for p in participants
        ],
    }


def _serialize_assignments(rows: list[WorkplaceAssignment]) -> list[dict]:
    return [
        {
            "id": a.id,
            "osgb_id": a.osgb_id,
            "company_id": a.company_id,
            "professional_id": a.professional_id,
            "professional_type": _enum_val(a.professional_type),
            "start_date": _dt(a.start_date),
            "end_date": _dt(a.end_date),
            "status": _enum_val(a.status),
            "isg_katip_contract_number": a.isg_katip_contract_number,
            "contract_storage_path": a.contract_storage_path,
        }
        for a in rows
    ]


def _serialize_contracts(rows: list[ServiceContract]) -> list[dict]:
    return [
        {
            "id": c.id,
            "osgb_id": c.osgb_id,
            "company_id": c.company_id,
            "contract_number": c.contract_number,
            "start_date": _dt(c.start_date),
            "end_date": _dt(c.end_date),
            "monthly_fee": c.monthly_fee,
            "status": c.status,
        }
        for c in rows
    ]


def _serialize_incidents(rows: list[IncidentEvent]) -> list[dict]:
    return [
        {
            "id": i.id,
            "form_no": i.form_no,
            "company_id": i.company_id,
            "event_type": i.event_type,
            "status": i.status,
            "event_date": _dt(i.event_date),
            "location": i.location,
            "short_summary": i.short_summary,
            "detail": i.detail,
            "risk_score": i.risk_score,
            "risk_level": i.risk_level,
        }
        for i in rows
    ]


def create_tenant_backup(
    db: Session,
    *,
    user: User,
    osgb_id: int | None = None,
    company_id: int | None = None,
) -> EisaArchiveRecord:
    """Kurum / OSGB kapsamındaki metadata + dosyaları tarihli zip olarak arşivle."""
    if user.role.value == "global_admin":
        target_osgb = osgb_id
        target_company = company_id
    else:
        target_osgb = user.osgb_id
        target_company = company_id or user.company_id

    if not target_osgb and not target_company:
        raise ValueError("Yedek için OSGB veya firma kapsamı gerekli.")

    companies: list[Company] = []
    if target_company:
        c = db.get(Company, target_company)
        if not c:
            raise ValueError("Firma bulunamadı.")
        if target_osgb and c.osgb_id and c.osgb_id != target_osgb:
            raise ValueError("Firma bu OSGB kapsamında değil.")
        companies = [c]
        target_osgb = target_osgb or c.osgb_id
    elif target_osgb:
        companies = list(
            db.scalars(select(Company).where(Company.osgb_id == target_osgb).order_by(Company.name)).all()
        )

    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    folder = archive_root() / "backups" / f"osgb-{target_osgb or 0}"
    folder.mkdir(parents=True, exist_ok=True)
    zip_name = f"backup-{stamp}-{uuid4().hex[:8]}.zip"
    zip_path = folder / zip_name

    org = db.get(OsgbOrganization, target_osgb) if target_osgb else None
    company_ids = [c.id for c in companies]
    docs: list[DocumentRecord] = []
    employees: list[Employee] = []
    health_rows: list[HealthRecord] = []
    risk_rows: list[RiskAssessment] = []
    training_rows: list[TrainingSession] = []
    participant_rows: list[TrainingParticipant] = []
    assignment_rows: list[WorkplaceAssignment] = []
    contract_rows: list[ServiceContract] = []
    incident_rows: list[IncidentEvent] = []

    if company_ids:
        docs = list(
            db.scalars(select(DocumentRecord).where(DocumentRecord.company_id.in_(company_ids))).all()
        )
        employees = list(
            db.scalars(select(Employee).where(Employee.company_id.in_(company_ids))).all()
        )
        health_rows = list(
            db.scalars(select(HealthRecord).where(HealthRecord.company_id.in_(company_ids))).all()
        )
        risk_rows = list(
            db.scalars(select(RiskAssessment).where(RiskAssessment.company_id.in_(company_ids))).all()
        )
        training_rows = list(
            db.scalars(select(TrainingSession).where(TrainingSession.company_id.in_(company_ids))).all()
        )
        if training_rows:
            tids = [t.id for t in training_rows]
            participant_rows = list(
                db.scalars(select(TrainingParticipant).where(TrainingParticipant.training_id.in_(tids))).all()
            )
        incident_rows = list(
            db.scalars(select(IncidentEvent).where(IncidentEvent.company_id.in_(company_ids))).all()
        )
        assignment_rows = list(
            db.scalars(
                select(WorkplaceAssignment).where(WorkplaceAssignment.company_id.in_(company_ids))
            ).all()
        )
        contract_rows = list(
            db.scalars(select(ServiceContract).where(ServiceContract.company_id.in_(company_ids))).all()
        )
    elif target_osgb:
        assignment_rows = list(
            db.scalars(select(WorkplaceAssignment).where(WorkplaceAssignment.osgb_id == target_osgb)).all()
        )
        contract_rows = list(
            db.scalars(select(ServiceContract).where(ServiceContract.osgb_id == target_osgb)).all()
        )

    domain_counts = {
        "documents": len(docs),
        "employees": len(employees),
        "health_records": len(health_rows),
        "risk_assessments": len(risk_rows),
        "training_sessions": len(training_rows),
        "training_participants": len(participant_rows),
        "workplace_assignments": len(assignment_rows),
        "service_contracts": len(contract_rows),
        "incident_events": len(incident_rows),
    }
    manifest = {
        "format_version": 3,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "created_by": user.email,
        "osgb_id": target_osgb,
        "osgb_name": org.name if org else None,
        "companies": [{"id": c.id, "name": c.name} for c in companies],
        "domain_counts": domain_counts,
        "restore": {
            "supports_file_restore": True,
            "supports_db_row_restore": False,
            "notes": "Dosya restore BACKUP_RESTORE_ENABLED ile; domain JSON export salt okunur (DB restore yok).",
        },
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", _json_bytes(manifest))
        zf.writestr(
            "documents.json",
            _json_bytes(
                [
                    {
                        "id": d.id,
                        "company_id": d.company_id,
                        "title": d.title,
                        "file_name": d.file_name,
                        "category": _enum_val(d.category),
                        "description": d.description,
                        "is_active": d.is_active,
                        "created_at": _dt(d.created_at),
                    }
                    for d in docs
                ]
            ),
        )
        zf.writestr(
            "employees.json",
            _json_bytes(
                [
                    {
                        "id": e.id,
                        "company_id": e.company_id,
                        "full_name": e.full_name,
                        "job_title": e.job_title,
                        "is_active": e.is_active,
                    }
                    for e in employees
                ]
            ),
        )
        zf.writestr("health_records.json", _json_bytes(_serialize_health(health_rows)))
        zf.writestr("risk_assessments.json", _json_bytes(_serialize_risks(risk_rows)))
        zf.writestr("trainings.json", _json_bytes(_serialize_trainings(training_rows, participant_rows)))
        zf.writestr("workplace_assignments.json", _json_bytes(_serialize_assignments(assignment_rows)))
        zf.writestr("service_contracts.json", _json_bytes(_serialize_contracts(contract_rows)))
        zf.writestr("incident_events.json", _json_bytes(_serialize_incidents(incident_rows)))
        root = upload_root()
        for cid in company_ids:
            company_dir = root / str(cid)
            if not company_dir.exists():
                continue
            for path in company_dir.rglob("*"):
                if path.is_file():
                    arcname = f"files/{cid}/{path.relative_to(company_dir).as_posix()}"
                    zf.write(path, arcname)
        if target_osgb:
            for sub in ("assignments", "visits"):
                osgb_dir = root / str(target_osgb) / sub
                if not osgb_dir.exists():
                    continue
                for path in osgb_dir.rglob("*"):
                    if path.is_file():
                        arcname = f"osgb_files/{sub}/{path.relative_to(osgb_dir).as_posix()}"
                        zf.write(path, arcname)

    zip_path = _maybe_encrypt_file(zip_path)
    zip_name = zip_path.name

    row = EisaArchiveRecord(
        kind=ArchiveKind.TENANT_BACKUP,
        osgb_id=target_osgb,
        company_id=target_company,
        entity_type="tenant_backup",
        entity_id=str(target_osgb or target_company),
        original_name=zip_name,
        storage_path=_rel_store(zip_path),
        size_bytes=zip_path.stat().st_size,
        checksum=_checksum(zip_path),
        notes=(
            f"Tenant yedek v3 — {len(companies)} işyeri, "
            f"{domain_counts['documents']} doküman, {domain_counts['health_records']} sağlık, "
            f"{domain_counts['risk_assessments']} risk, {domain_counts['training_sessions']} eğitim"
        ),
        created_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def resolve_archive_path(row: EisaArchiveRecord) -> Path:
    path = (archive_root() / row.storage_path).resolve()
    if archive_root() not in path.parents and path != archive_root():
        raise FileNotFoundError("Geçersiz arşiv yolu.")
    if not path.exists():
        raise FileNotFoundError("Arşiv dosyası bulunamadı.")
    return path
