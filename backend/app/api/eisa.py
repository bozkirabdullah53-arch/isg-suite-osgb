"""EİSA — platform üst yönetimi: OSGB başvuru onayı ve abonelik yönetimi."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import (
    OsgbApplication,
    OsgbApplicationStatus,
    OsgbOrganization,
    OsgbSubscription,
    PaymentChannel,
    SubscriptionStatus,
    User,
    UserRole,
)
from app.schemas.osgb_subscription import (
    OsgbApplicationReject,
    OsgbApplicationResponse,
    OsgbSubscriptionResponse,
    OsgbSubscriptionUpdate,
)
from app.services.osgb_subscription import (
    approve_application,
    effective_subscription_status,
    get_or_create_subscription,
    subscription_allows_write,
)

router = APIRouter(prefix="/eisa", tags=["EİSA Platform"])


def _sub_response(db: Session, sub: OsgbSubscription) -> OsgbSubscriptionResponse:
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


@router.get("/applications", response_model=list[OsgbApplicationResponse])
def list_applications(
    status: str | None = "pending",
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    stmt = select(OsgbApplication).order_by(OsgbApplication.created_at.desc())
    if status:
        try:
            st = OsgbApplicationStatus(status)
            stmt = stmt.where(OsgbApplication.status == st)
        except ValueError:
            pass
    return list(db.scalars(stmt).all())


@router.post("/applications/{application_id}/approve", response_model=OsgbApplicationResponse)
def approve(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    app_row = db.get(OsgbApplication, application_id)
    if not app_row:
        raise HTTPException(404, "Başvuru bulunamadı.")
    approve_application(db, app_row, user)
    db.refresh(app_row)
    return app_row


@router.post("/applications/{application_id}/reject", response_model=OsgbApplicationResponse)
def reject(
    application_id: int,
    payload: OsgbApplicationReject,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    app_row = db.get(OsgbApplication, application_id)
    if not app_row:
        raise HTTPException(404, "Başvuru bulunamadı.")
    if app_row.status != OsgbApplicationStatus.PENDING:
        raise HTTPException(400, "Başvuru zaten işlenmiş.")
    app_row.status = OsgbApplicationStatus.REJECTED
    app_row.rejection_reason = payload.reason.strip()
    app_row.reviewed_by_user_id = user.id
    app_row.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(app_row)
    return app_row


@router.get("/subscriptions", response_model=list[OsgbSubscriptionResponse])
def list_subscriptions(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    rows = list(db.scalars(select(OsgbSubscription).order_by(OsgbSubscription.updated_at.desc())).all())
    return [_sub_response(db, r) for r in rows]


@router.get("/subscriptions/{osgb_id}", response_model=OsgbSubscriptionResponse)
def get_subscription(
    osgb_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    sub = db.scalar(select(OsgbSubscription).where(OsgbSubscription.osgb_id == osgb_id))
    if not sub:
        if not db.get(OsgbOrganization, osgb_id):
            raise HTTPException(404, "OSGB bulunamadı.")
        sub = get_or_create_subscription(db, osgb_id)
    return _sub_response(db, sub)


@router.put("/subscriptions/{osgb_id}", response_model=OsgbSubscriptionResponse)
def update_subscription(
    osgb_id: int,
    payload: OsgbSubscriptionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    if not db.get(OsgbOrganization, osgb_id):
        raise HTTPException(404, "OSGB bulunamadı.")
    sub = get_or_create_subscription(db, osgb_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"]:
        try:
            sub.status = SubscriptionStatus(data["status"])
        except ValueError as exc:
            raise HTTPException(422, "Geçersiz abonelik durumu.") from exc
    if "last_payment_channel" in data:
        ch = data["last_payment_channel"]
        sub.last_payment_channel = PaymentChannel(ch) if ch else None
    for key in ("trial_ends_at", "current_period_ends_at", "max_users", "max_workplaces", "payment_notes", "is_auto_renew"):
        if key in data:
            setattr(sub, key, data[key])
    sub.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sub)
    return _sub_response(db, sub)


@router.get("/dashboard")
def eisa_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    from sqlalchemy import func

    pending_count = db.scalar(
        select(func.count()).select_from(OsgbApplication).where(
            OsgbApplication.status == OsgbApplicationStatus.PENDING
        )
    ) or 0
    osgb_count = db.scalar(select(func.count()).select_from(OsgbOrganization)) or 0
    sub_count = db.scalar(select(func.count()).select_from(OsgbSubscription)) or 0
    return {
        "platform": "EİSA",
        "pending_applications": pending_count,
        "osgb_total": osgb_count,
        "subscriptions_total": sub_count,
    }
