from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

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


def ensure_access(user: User, company_id: int) -> None:
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Bu firmanın dokümanlarına erişemezsiniz.")


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    company_id: int | None = None,
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(DocumentRecord).order_by(DocumentRecord.created_at.desc())
    effective_company = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if effective_company:
        query = query.where(DocumentRecord.company_id == effective_company)
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
    ensure_access(user, payload.company_id)
    record = DocumentRecord(**payload.model_dump(), created_by_id=user.id)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
