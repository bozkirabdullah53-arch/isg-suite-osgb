from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Company, CompanySubscription, SubscriptionPlan, SubscriptionStatus, User, UserRole
from app.schemas.subscription import SubscriptionResponse, SubscriptionUpdate

router = APIRouter(prefix="/subscriptions", tags=["Abonelik"])


def get_or_create(db: Session, company_id: int) -> CompanySubscription:
    subscription = db.scalar(select(CompanySubscription).where(CompanySubscription.company_id == company_id))
    if subscription:
        return subscription
    subscription = CompanySubscription(
        company_id=company_id,
        plan=SubscriptionPlan.DEMO,
        status=SubscriptionStatus.TRIAL,
        trial_ends_at=datetime.utcnow() + timedelta(days=14),
        max_users=3,
        max_employees=50,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


@router.get("/current", response_model=SubscriptionResponse)
def current_subscription(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    effective_company = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if not effective_company:
        raise HTTPException(status_code=400, detail="Firma seçilmelidir.")
    if not db.get(Company, effective_company):
        raise HTTPException(status_code=404, detail="Firma bulunamadı.")
    return get_or_create(db, effective_company)


@router.put("/{company_id}", response_model=SubscriptionResponse)
def update_subscription(
    company_id: int,
    payload: SubscriptionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    subscription = get_or_create(db, company_id)
    for key, value in payload.model_dump().items():
        setattr(subscription, key, value)
    db.commit()
    db.refresh(subscription)
    return subscription
