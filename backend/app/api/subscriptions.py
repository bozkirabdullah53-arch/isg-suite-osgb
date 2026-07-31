from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Company, CompanySubscription, OsgbSubscription, SubscriptionPlan, SubscriptionStatus, User, UserRole
from app.schemas.osgb_subscription import OsgbSubscriptionResponse
from app.schemas.subscription import SubscriptionResponse, SubscriptionUpdate
from app.services.osgb_subscription import (
    effective_subscription_status,
    get_or_create_subscription,
    resolve_user_osgb_id,
    subscription_allows_write,
)

router = APIRouter(prefix="/subscriptions", tags=["Abonelik"])


def _osgb_sub_response(db: Session, sub: OsgbSubscription) -> OsgbSubscriptionResponse:
    from app.models.entities import OsgbOrganization

    org = db.get(OsgbOrganization, sub.osgb_id)
    eff = effective_subscription_status(sub)
    return OsgbSubscriptionResponse(
        id=sub.id,
        osgb_id=sub.osgb_id,
        osgb_name=org.name if org else None,
        plan=sub.plan.value,
        status=sub.status.value,
        effective_status=eff.value,
        write_allowed=subscription_allows_write(sub),
        trial_ends_at=sub.trial_ends_at,
        current_period_ends_at=sub.current_period_ends_at,
        max_users=sub.max_users,
        max_workplaces=sub.max_workplaces,
        last_payment_channel=sub.last_payment_channel.value if sub.last_payment_channel else None,
        payment_notes=sub.payment_notes,
        is_auto_renew=sub.is_auto_renew,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


@router.get("/osgb/current", response_model=OsgbSubscriptionResponse)
def osgb_current_subscription(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == UserRole.GLOBAL_ADMIN:
        if not osgb_id:
            raise HTTPException(status_code=400, detail="EİSA için osgb_id parametresi gerekli.")
        oid = osgb_id
    else:
        oid = resolve_user_osgb_id(db, user)
        if not oid:
            raise HTTPException(status_code=400, detail="OSGB kapsamı bulunamadı.")
    return _osgb_sub_response(db, get_or_create_subscription(db, oid))


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
