from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import DocumentRecord, User, UserRole
from app.schemas.document import DocumentCreate, DocumentResponse

router = APIRouter(prefix="/documents", tags=["Dokümanlar"])

EDIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
)


def ensure_access(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    company_id: int | None = None,
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(DocumentRecord).order_by(DocumentRecord.created_at.desc())
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    if company_ids is not None:
        query = query.where(DocumentRecord.company_id.in_(company_ids))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(DocumentRecord.title.ilike(pattern), DocumentRecord.description.ilike(pattern)))
    return list(db.scalars(query).all())


@router.post("", response_model=DocumentResponse)
def create_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_access(db, user, payload.company_id)
    record = DocumentRecord(**payload.model_dump(), created_by_id=user.id)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{document_id}/deactivate", response_model=DocumentResponse)
def deactivate_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Dokümanı pasife alır; bağlı dosya merkezi arşive kopyalanır (EİSA erişimi)."""
    from pathlib import Path

    from app.core.config import settings
    from app.services.archive_store import archive_file_before_delete

    record = db.get(DocumentRecord, document_id)
    if not record:
        raise HTTPException(404, "Doküman bulunamadı.")
    ensure_access(db, user, record.company_id)

    marker = "[stored:"
    desc = record.description or ""
    if marker in desc:
        stored_name = desc.split(marker, 1)[1].split("]", 1)[0]
        path = (Path(settings.upload_dir).resolve() / str(record.company_id) / stored_name)
        try:
            archive_file_before_delete(
                db,
                source=path,
                user=user,
                company_id=record.company_id,
                entity_type="document",
                entity_id=str(record.id),
                original_name=record.file_name,
                notes="Doküman pasife alınmadan önce arşivlendi",
            )
        except Exception:
            pass
    record.is_active = False
    db.commit()
    db.refresh(record)
    return record
