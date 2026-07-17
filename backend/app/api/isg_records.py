from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import IsgModule, IsgRecord, User, UserRole
from app.schemas.isg_record import IsgRecordCreate, IsgRecordResponse, IsgRecordUpdate

router = APIRouter(prefix="/isg-records", tags=["İSG Modülleri"])

EDIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
)


def ensure_company_access(user: User, company_id: int) -> None:
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Bu firmanın kayıtlarına erişemezsiniz.")


@router.get("", response_model=list[IsgRecordResponse])
def list_records(
    module: IsgModule | None = None,
    q: str | None = Query(default=None, max_length=100),
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(IsgRecord).order_by(IsgRecord.created_at.desc())
    effective_company = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if effective_company:
        query = query.where(IsgRecord.company_id == effective_company)
    if module:
        query = query.where(IsgRecord.module == module)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(IsgRecord.title.ilike(pattern), IsgRecord.description.ilike(pattern)))
    return list(db.scalars(query).all())


@router.post("", response_model=IsgRecordResponse)
def create_record(
    payload: IsgRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_company_access(user, payload.company_id)
    values = payload.model_dump()
    if payload.module == IsgModule.RISK and payload.probability and payload.impact:
        values["risk_score"] = payload.probability * payload.impact
    record = IsgRecord(**values, created_by_id=user.id)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{record_id}", response_model=IsgRecordResponse)
def update_record(
    record_id: int,
    payload: IsgRecordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    record = db.get(IsgRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
    ensure_company_access(user, record.company_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record
