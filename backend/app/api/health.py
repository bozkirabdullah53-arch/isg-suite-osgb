from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Employee, HealthRecord, User, UserRole
from app.schemas.health import HealthRecordCreate, HealthRecordResponse

router = APIRouter(prefix="/health-records", tags=["Sağlık Kayıtları"])

HEALTH_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.WORKPLACE_PHYSICIAN,
)


def ensure_access(user: User, company_id: int) -> None:
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Bu firmanın sağlık kayıtlarına erişemezsiniz.")


@router.get("", response_model=list[HealthRecordResponse])
def list_health_records(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    query = select(HealthRecord).order_by(HealthRecord.examination_date.desc())
    effective_company = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if effective_company:
        query = query.where(HealthRecord.company_id == effective_company)
    return list(db.scalars(query).all())


@router.post("", response_model=HealthRecordResponse)
def create_health_record(
    payload: HealthRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    ensure_access(user, payload.company_id)
    employee = db.get(Employee, payload.employee_id)
    if not employee or employee.company_id != payload.company_id:
        raise HTTPException(status_code=400, detail="Personel ve firma eşleşmiyor.")
    record = HealthRecord(**payload.model_dump(), created_by_id=user.id)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
