from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.contractor import ContractorCompany, ContractorDocument, ContractorWorker
from app.models.entities import AuditLog, DocumentCategory, DocumentRecord, User, UserRole
from app.models.work_permit import WorkPermit

router = APIRouter(tags=["Taşeron Yönetimi"])
FIELD_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.OTHER_HEALTH_PERSONNEL,
)


class ContractorWorkerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    national_id_masked: str | None = Field(default=None, max_length=20)
    job_title: str | None = Field(default=None, max_length=120)


class ContractorDeactivateRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


def _load_contractor(db: Session, user: User, contractor_id: int) -> ContractorCompany:
    row = db.get(ContractorCompany, contractor_id)
    if not row:
        raise HTTPException(404, "Taşeron firması bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    return row


def _audit(db: Session, user: User, company_id: int, action: str, entity_type: str, entity_id: int, description: str) -> None:
    db.add(
        AuditLog(
            user_id=user.id,
            company_id=company_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            description=description[:1200],
            module="contractor",
        )
    )


@router.post("/{contractor_id}/workers")
def add_worker(
    contractor_id: int,
    payload: ContractorWorkerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_ROLES)),
):
    contractor = _load_contractor(db, user, contractor_id)
    if not contractor.is_active:
        raise HTTPException(409, "Pasif taşerona çalışan eklenemez.")
    worker = ContractorWorker(
        contractor_id=contractor.id,
        full_name=payload.full_name.strip(),
        national_id_masked=payload.national_id_masked,
        job_title=payload.job_title,
    )
    db.add(worker)
    db.flush()
    _audit(db, user, contractor.company_id, "contractor_worker_added", "contractor_worker", worker.id, "Taşeron çalışanı eklendi.")
    db.commit()
    db.refresh(worker)
    return {"id": worker.id, "full_name": worker.full_name, "job_title": worker.job_title, "is_active": worker.is_active}


@router.patch("/{contractor_id}/workers/{worker_id}/deactivate")
def deactivate_worker(
    contractor_id: int,
    worker_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_ROLES)),
):
    contractor = _load_contractor(db, user, contractor_id)
    worker = db.scalar(
        select(ContractorWorker).where(
            ContractorWorker.id == worker_id,
            ContractorWorker.contractor_id == contractor.id,
            ContractorWorker.is_active.is_(True),
        )
    )
    if not worker:
        raise HTTPException(404, "Aktif taşeron çalışanı bulunamadı.")
    worker.is_active = False
    _audit(db, user, contractor.company_id, "contractor_worker_deactivated", "contractor_worker", worker.id, "Taşeron çalışanı pasife alındı.")
    db.commit()
    return {"ok": True, "worker_id": worker.id}


@router.patch("/{contractor_id}/deactivate")
def deactivate_contractor(
    contractor_id: int,
    payload: ContractorDeactivateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_ROLES)),
):
    contractor = _load_contractor(db, user, contractor_id)
    if not contractor.is_active:
        return {"ok": True, "contractor_id": contractor.id, "already_inactive": True}
    contractor.is_active = False
    note = "Taşeron firması pasife alındı."
    if payload.reason:
        note += f" Gerekçe: {payload.reason.strip()}"
    _audit(db, user, contractor.company_id, "contractor_deactivated", "contractor_company", contractor.id, note)
    db.commit()
    return {"ok": True, "contractor_id": contractor.id}


@router.get("/{contractor_id}/permits")
def list_attached_permits(
    contractor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_ROLES)),
):
    contractor = _load_contractor(db, user, contractor_id)
    permits = db.scalars(
        select(WorkPermit)
        .where(WorkPermit.contractor_id == contractor.id, WorkPermit.company_id == contractor.company_id)
        .order_by(WorkPermit.created_at.desc())
    ).all()
    return {
        "items": [
            {
                "id": permit.id,
                "permit_type": permit.permit_type,
                "description": permit.description,
                "status": permit.status,
                "valid_from": permit.valid_from,
                "valid_until": permit.valid_until,
            }
            for permit in permits
        ]
    }


@router.post("/{contractor_id}/documents/{document_id}/copy-to-documents")
def copy_document_to_registry(
    contractor_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_ROLES)),
):
    contractor = _load_contractor(db, user, contractor_id)
    document = db.scalar(
        select(ContractorDocument).where(
            ContractorDocument.id == document_id,
            ContractorDocument.contractor_id == contractor.id,
            ContractorDocument.is_active.is_(True),
        )
    )
    if not document:
        raise HTTPException(404, "Taşeron belgesi bulunamadı.")
    if document.document_record_id:
        existing = db.get(DocumentRecord, document.document_record_id)
        if existing:
            return {"ok": True, "document_record_id": existing.id, "already_copied": True}

    record = DocumentRecord(
        company_id=contractor.company_id,
        category=DocumentCategory.GENERAL,
        title=f"Taşeron - {contractor.name} - {document.title}"[:220],
        file_name=document.file_name,
        description=(
            f"Taşeron belge kaydından kopyalandı. Kaynak taşeron belge #{document.id}. "
            "Dosyanın güvenli aslı Taşeron Yönetimi depolamasında korunur."
        ),
        valid_until=document.valid_until,
        version="1.0",
        created_by_id=user.id,
    )
    db.add(record)
    db.flush()
    document.document_record_id = record.id
    _audit(db, user, contractor.company_id, "contractor_document_copied_to_registry", "contractor_document", document.id, f"Belge Dokümanlar kayıt defterine #{record.id} olarak kopyalandı.")
    db.commit()
    return {"ok": True, "document_record_id": record.id, "already_copied": False}
