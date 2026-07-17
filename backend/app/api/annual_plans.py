from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import AnnualPlanItem, User, UserRole
from app.schemas.annual_plan import AnnualPlanCreate, AnnualPlanResponse

router = APIRouter(prefix="/annual-plans", tags=["Yıllık Planlar"])

EDIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
)


def ensure_access(user: User, company_id: int) -> None:
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Bu firmanın yıllık planına erişemezsiniz.")


@router.get("", response_model=list[AnnualPlanResponse])
def list_plan_items(
    year: int | None = None,
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(AnnualPlanItem).order_by(AnnualPlanItem.year.desc(), AnnualPlanItem.month)
    effective_company = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if effective_company:
        query = query.where(AnnualPlanItem.company_id == effective_company)
    if year:
        query = query.where(AnnualPlanItem.year == year)
    return list(db.scalars(query).all())


@router.post("", response_model=AnnualPlanResponse)
def create_plan_item(
    payload: AnnualPlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_access(user, payload.company_id)
    item = AnnualPlanItem(**payload.model_dump(), created_by_id=user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
