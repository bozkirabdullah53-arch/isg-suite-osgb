from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.contractor import ContractorCompany, ContractorDocument, ContractorWorker
from app.models.entities import AuditLog, Company, User, UserRole
from app.models.work_permit import WorkPermit
from app.schemas.contractor import ContractorCreate, ContractorDocumentCreate
from app.services.object_store import get_object_store
from app.services.object_upload_commit import commit_object_upload
from app.services.stored_files import response_for_storage_key
from app.services.upload_security import assert_safe_upload
from app.core.config import settings

router = APIRouter(prefix="/contractors", tags=["Taşeron Yönetimi"])
READ_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.OTHER_HEALTH_PERSONNEL)
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.OTHER_HEALTH_PERSONNEL)


def _load(db: Session, user: User, contractor_id: int) -> ContractorCompany:
    row = db.get(ContractorCompany, contractor_id)
    if not row:
        raise HTTPException(404, "Taşeron firması bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    return row


def _payload(db: Session, row: ContractorCompany) -> dict:
    workers = db.scalars(select(ContractorWorker).where(ContractorWorker.contractor_id == row.id, ContractorWorker.is_active.is_(True)).order_by(ContractorWorker.full_name)).all()
    documents = db.scalars(select(ContractorDocument).where(ContractorDocument.contractor_id == row.id, ContractorDocument.is_active.is_(True)).order_by(ContractorDocument.valid_until)).all()
    return {"id": row.id, "company_id": row.company_id, "name": row.name, "contract_number": row.contract_number, "contract_start": row.contract_start, "contract_end": row.contract_end, "contact_name": row.contact_name, "contact_phone": row.contact_phone, "is_active": row.is_active, "workers": [{"id": item.id, "full_name": item.full_name, "national_id_masked": item.national_id_masked, "job_title": item.job_title} for item in workers], "documents": [{"id": item.id, "document_type": item.document_type, "title": item.title, "file_name": item.file_name, "valid_until": item.valid_until, "notes": item.notes, "has_file": bool(item.storage_key), "document_record_id": item.document_record_id} for item in documents]}


def _audit(db: Session, user: User, company_id: int, action: str, entity_type: str, entity_id: int, description: str) -> None:
    db.add(AuditLog(user_id=user.id, company_id=company_id, action=action, entity_type=entity_type, entity_id=str(entity_id), description=description[:1200], module="contractor"))


@router.get("")
def list_contractors(company_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return {"items": []}
    stmt = select(ContractorCompany).where(ContractorCompany.is_active.is_(True)).order_by(ContractorCompany.name)
    if company_ids is not None: stmt = stmt.where(ContractorCompany.company_id.in_(company_ids))
    return {"items": [_payload(db, row) for row in db.scalars(stmt).all()]}


@router.post("")
def create_contractor(payload: ContractorCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    ensure_company_access(db, user, payload.company_id)
    if not db.get(Company, payload.company_id): raise HTTPException(404, "İşyeri bulunamadı.")
    row = ContractorCompany(company_id=payload.company_id, name=payload.name, contract_number=payload.contract_number, contract_start=payload.contract_start, contract_end=payload.contract_end, contact_name=payload.contact_name, contact_phone=payload.contact_phone, created_by_id=user.id)
    row.workers = [ContractorWorker(full_name=item.full_name.strip(), national_id_masked=item.national_id_masked, job_title=item.job_title) for item in payload.workers]
    db.add(row); db.flush(); _audit(db, user, row.company_id, "contractor_created", "contractor_company", row.id, "Taşeron firması oluşturuldu."); db.commit(); db.refresh(row)
    return _payload(db, row)


@router.get("/{contractor_id}")
def get_contractor(contractor_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return _payload(db, _load(db, user, contractor_id))


@router.post("/{contractor_id}/documents")
def add_document(contractor_id: int, payload: ContractorDocumentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, contractor_id)
    if not row.is_active: raise HTTPException(409, "Pasif taşerona yeni belge eklenemez.")
    document = ContractorDocument(contractor_id=row.id, document_type=payload.document_type.strip(), title=payload.title.strip(), file_name=payload.file_name, valid_until=payload.valid_until, notes=payload.notes, created_by_id=user.id)
    db.add(document); db.flush(); _audit(db, user, row.company_id, "contractor_document_added", "contractor_document", document.id, "Taşeron belgesi kaydedildi."); db.commit()
    return {"id": document.id, "valid_until": document.valid_until, "is_expired": bool(document.valid_until and document.valid_until < date.today())}


@router.post("/{contractor_id}/documents/{document_id}/file")
async def upload_document_file(contractor_id: int, document_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    contractor = _load(db, user, contractor_id)
    if not contractor.is_active: raise HTTPException(409, "Pasif taşeron belgesi güncellenemez.")
    document = db.scalar(select(ContractorDocument).where(ContractorDocument.id == document_id, ContractorDocument.contractor_id == contractor.id, ContractorDocument.is_active.is_(True)))
    if not document:
        raise HTTPException(404, "Taşeron belgesi bulunamadı.")
    original_name = Path(file.filename or "belge").name[:255]
    extension = Path(original_name).suffix.lower()
    if extension not in {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx"}:
        raise HTTPException(415, "Yalnızca PDF, PNG, JPG, DOCX veya XLSX kabul edilir.")
    limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    assert_safe_upload(content, extension, original_name)
    key = f"{contractor.company_id}/contractors/{contractor.id}/documents/{document.id}/{__import__('uuid').uuid4().hex}{extension}"
    old_key = document.storage_key
    store = get_object_store()
    store.put_bytes(key, content)
    document.storage_key = key; document.file_name = original_name; document.content_type = (file.content_type or "application/octet-stream")[:120]; document.file_size = len(content)
    _audit(db, user, contractor.company_id, "contractor_document_file_uploaded", "contractor_document", document.id, "Taşeron belgesi güvenli depolamaya alındı.")
    commit_object_upload(db, store, key, old_key=old_key)
    return {"id": document.id, "file_name": document.file_name, "file_size": document.file_size}


@router.get("/{contractor_id}/documents/{document_id}/file")
def download_document_file(contractor_id: int, document_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    contractor = _load(db, user, contractor_id)
    document = db.scalar(select(ContractorDocument).where(ContractorDocument.id == document_id, ContractorDocument.contractor_id == contractor.id, ContractorDocument.is_active.is_(True)))
    if not document or not document.storage_key:
        raise HTTPException(404, "Taşeron belgesi dosyası bulunamadı.")
    _audit(db, user, contractor.company_id, "contractor_document_file_viewed", "contractor_document", document.id, "Taşeron belgesi görüntülendi.")
    db.commit()
    return response_for_storage_key(document.storage_key, filename=document.file_name, media_type=document.content_type or "application/octet-stream")


@router.get("/{contractor_id}/eligibility")
def contractor_eligibility(contractor_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    row = _load(db, user, contractor_id)
    missing = []
    if not row.is_active: missing.append("Taşeron firma pasif")
    if row.contract_end and row.contract_end < date.today(): missing.append("Sözleşme süresi dolmuş")
    docs = db.scalars(select(ContractorDocument).where(ContractorDocument.contractor_id == row.id, ContractorDocument.is_active.is_(True))).all()
    if not docs: missing.append("Belge kaydı bulunmuyor")
    if any(item.valid_until and item.valid_until < date.today() for item in docs): missing.append("Süresi dolmuş belge var")
    if not db.scalar(select(ContractorWorker.id).where(ContractorWorker.contractor_id == row.id, ContractorWorker.is_active.is_(True))): missing.append("Aktif taşeron çalışanı bulunmuyor")
    return {"eligible": not missing, "reasons": missing}


@router.post("/{contractor_id}/permits/{permit_id}")
def attach_permit(contractor_id: int, permit_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    contractor = _load(db, user, contractor_id)
    if not contractor.is_active: raise HTTPException(409, "Pasif taşeron çalışma iznine bağlanamaz.")
    permit = db.get(WorkPermit, permit_id)
    if not permit or permit.company_id != contractor.company_id: raise HTTPException(404, "Çalışma izni bulunamadı.")
    permit.contractor_id = contractor.id
    _audit(db, user, contractor.company_id, "contractor_attached_to_permit", "work_permit", permit.id, "Taşeron çalışma iznine bağlandı.")
    db.commit()
    return {"ok": True, "contractor_id": contractor.id, "permit_id": permit.id}


from app.api.contractors_phase_b import router as phase_b_router
router.include_router(phase_b_router)
