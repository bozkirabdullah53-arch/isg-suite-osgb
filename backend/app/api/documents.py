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
