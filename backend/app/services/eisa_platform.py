"""EİSA platform yardımcıları — dashboard, abonelik zenginleştirme, ayarlar."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AuditLog,
    EisaPackage,
    EisaPaymentStatus,
    EisaPlatformSetting,
    EisaSubscriptionPayment,
    OsgbApplication,
    OsgbApplicationStatus,
    OsgbOrganization,
    OsgbSubscription,
    SubscriptionStatus,
    User,
)
from app.schemas.eisa_platform import EisaOsgbUserResponse
from app.schemas.osgb_subscription import OsgbSubscriptionResponse
from app.services.osgb_subscription import effective_subscription_status, subscription_allows_write

EXPIRING_WINDOW_DAYS = 14
DEFAULT_SETTINGS = {
    "trial_days": "10",
    "expiring_window_days": "14",
    "support_email": "destek@eisa.com.tr",
    "support_phone": "",
}


def get_setting(db: Session, key: str, default: str = "") -> str:
    try:
        row = db.scalar(select(EisaPlatformSetting).where(EisaPlatformSetting.key == key))
        if row:
            return row.value
    except Exception:
        pass
    return DEFAULT_SETTINGS.get(key, default)


def get_settings(db: Session) -> dict[str, str]:
    out = dict(DEFAULT_SETTINGS)
    try:
        rows = db.scalars(select(EisaPlatformSetting)).all()
        for row in rows:
            out[row.key] = row.value
    except Exception:
        pass
    return out


def set_settings(db: Session, updates: dict[str, str]) -> dict[str, str]:
    for key, value in updates.items():
        row = db.scalar(select(EisaPlatformSetting).where(EisaPlatformSetting.key == key))
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
        else:
            db.add(EisaPlatformSetting(key=key, value=value, updated_at=datetime.utcnow()))
    db.commit()
    return get_settings(db)


def expiring_window_days(db: Session) -> int:
    try:
        return max(1, int(get_setting(db, "expiring_window_days", "14")))
    except ValueError:
        return EXPIRING_WINDOW_DAYS


def _end_date(sub: OsgbSubscription) -> datetime | None:
    if sub.status == SubscriptionStatus.TRIAL:
        return sub.trial_ends_at
    return sub.current_period_ends_at


def days_remaining(sub: OsgbSubscription, now: datetime | None = None) -> int | None:
    now = now or datetime.utcnow()
    end = _end_date(sub)
    if not end:
        return None
    delta = (end - now).days
    return max(0, delta) if delta >= 0 else delta


def is_expiring(sub: OsgbSubscription, window: int, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    eff = effective_subscription_status(sub, now)
    if eff in (SubscriptionStatus.PAST_DUE, SubscriptionStatus.SUSPENDED, SubscriptionStatus.CANCELLED):
        return False
    end = _end_date(sub)
    if not end or end < now:
        return False
    return end <= now + timedelta(days=window)


def is_expired(sub: OsgbSubscription, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return effective_subscription_status(sub, now) == SubscriptionStatus.PAST_DUE


def latest_payment(db: Session, osgb_id: int) -> EisaSubscriptionPayment | None:
    return db.scalar(
        select(EisaSubscriptionPayment)
        .where(EisaSubscriptionPayment.osgb_id == osgb_id)
        .order_by(EisaSubscriptionPayment.payment_date.desc(), EisaSubscriptionPayment.id.desc())
        .limit(1)
    )


def subscription_response(db: Session, sub: OsgbSubscription) -> OsgbSubscriptionResponse:
    org = db.get(OsgbOrganization, sub.osgb_id)
    pkg = db.get(EisaPackage, sub.package_id) if sub.package_id else None
    eff = effective_subscription_status(sub)
    pay = latest_payment(db, sub.osgb_id)
    return OsgbSubscriptionResponse(
        id=sub.id,
        osgb_id=sub.osgb_id,
        osgb_name=org.name if org else None,
        responsible_manager=org.responsible_manager if org else None,
        contact_email=org.email if org else None,
        contact_phone=org.phone if org else None,
        package_id=sub.package_id,
        package_name=pkg.name if pkg else None,
        plan=sub.plan.value,
        status=sub.status.value,
        effective_status=eff.value,
        write_allowed=subscription_allows_write(sub),
        days_remaining=days_remaining(sub),
        trial_ends_at=sub.trial_ends_at,
        current_period_ends_at=sub.current_period_ends_at,
        max_users=sub.max_users,
        max_workplaces=sub.max_workplaces,
        last_payment_channel=sub.last_payment_channel.value if sub.last_payment_channel else None,
        last_payment_date=pay.payment_date if pay else None,
        last_payment_amount=float(pay.amount) if pay else None,
        payment_status=pay.payment_status.value if pay else None,
        payment_notes=sub.payment_notes,
        is_auto_renew=sub.is_auto_renew,
        account_active=org.is_active if org else True,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


def osgb_user_response(db: Session, org: OsgbOrganization) -> EisaOsgbUserResponse:
    from app.services.osgb_admin import find_osgb_admin

    sub = db.scalar(select(OsgbSubscription).where(OsgbSubscription.osgb_id == org.id))
    pkg = db.get(EisaPackage, sub.package_id) if sub and sub.package_id else None
    eff = effective_subscription_status(sub) if sub else None
    admin = find_osgb_admin(db, org.id)
    return EisaOsgbUserResponse(
        id=org.id,
        name=org.name,
        authorization_number=org.authorization_number,
        tax_number=org.tax_number,
        responsible_manager=org.responsible_manager,
        contact_email=org.email,
        contact_phone=org.phone,
        is_active=org.is_active,
        archived_at=org.archived_at,
        subscription_status=sub.status.value if sub else None,
        effective_status=eff.value if eff else None,
        package_name=pkg.name if pkg else None,
        trial_ends_at=sub.trial_ends_at if sub else None,
        current_period_ends_at=sub.current_period_ends_at if sub else None,
        write_allowed=subscription_allows_write(sub) if sub else False,
        admin_email=admin.email if admin else None,
        admin_name=admin.full_name if admin else None,
        has_admin_user=admin is not None,
        created_at=org.created_at,
    )


def build_dashboard(db: Session) -> dict:
    now = datetime.utcnow()
    window = expiring_window_days(db)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    pending_count = db.scalar(
        select(func.count()).select_from(OsgbApplication).where(
            OsgbApplication.status == OsgbApplicationStatus.PENDING
        )
    ) or 0
    osgb_count = db.scalar(select(func.count()).select_from(OsgbOrganization)) or 0
    subs = list(db.scalars(select(OsgbSubscription)).all())

    active_count = 0
    expired_count = 0
    expiring_count = 0
    trial_count = 0
    suspended_count = 0

    for sub in subs:
        eff = effective_subscription_status(sub, now)
        if eff == SubscriptionStatus.TRIAL:
            trial_count += 1
        if eff in (SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE):
            active_count += 1
        if is_expired(sub, now):
            expired_count += 1
        if is_expiring(sub, window, now):
            expiring_count += 1
        if eff == SubscriptionStatus.SUSPENDED:
            suspended_count += 1

    payments_month = Decimal("0")
    payments_total = Decimal("0")
    pending_payments = 0
    failed_payments = 0
    try:
        payments_month = db.scalar(
            select(func.coalesce(func.sum(EisaSubscriptionPayment.amount), 0)).where(
                EisaSubscriptionPayment.payment_status == EisaPaymentStatus.COMPLETED,
                EisaSubscriptionPayment.payment_date >= month_start,
            )
        ) or Decimal("0")

        payments_total = db.scalar(
            select(func.coalesce(func.sum(EisaSubscriptionPayment.amount), 0)).where(
                EisaSubscriptionPayment.payment_status == EisaPaymentStatus.COMPLETED,
            )
        ) or Decimal("0")

        pending_payments = db.scalar(
            select(func.count()).select_from(EisaSubscriptionPayment).where(
                EisaSubscriptionPayment.payment_status == EisaPaymentStatus.PENDING
            )
        ) or 0

        failed_payments = db.scalar(
            select(func.count()).select_from(EisaSubscriptionPayment).where(
                EisaSubscriptionPayment.payment_status == EisaPaymentStatus.FAILED
            )
        ) or 0
    except Exception:
        pass

    return {
        "platform": "EİSA",
        "pending_applications": pending_count,
        "osgb_total": osgb_count,
        "subscriptions_total": len(subs),
        "active_subscriptions": active_count,
        "expired_subscriptions": expired_count,
        "expiring_subscriptions": expiring_count,
        "trial_subscriptions": trial_count,
        "suspended_accounts": suspended_count,
        "payments_this_month": float(payments_month),
        "payments_total_collected": float(payments_total),
        "pending_payments": pending_payments,
        "failed_payments": failed_payments,
        "upcoming_renewals": expiring_count,
        "expiring_window_days": window,
    }


def filter_subscriptions(
    db: Session,
    *,
    filter_type: str = "all",
    q: str | None = None,
) -> list[OsgbSubscriptionResponse]:
    now = datetime.utcnow()
    window = expiring_window_days(db)
    subs = list(db.scalars(select(OsgbSubscription).order_by(OsgbSubscription.updated_at.desc())).all())
    out: list[OsgbSubscriptionResponse] = []
    for sub in subs:
        if filter_type == "expiring" and not is_expiring(sub, window, now):
            continue
        if filter_type == "expired" and not is_expired(sub, now):
            continue
        resp = subscription_response(db, sub)
        if q:
            needle = q.strip().lower()
            hay = " ".join(
                filter(
                    None,
                    [
                        resp.osgb_name,
                        resp.contact_email,
                        resp.responsible_manager,
                        resp.package_name,
                    ],
                )
            ).lower()
            if needle not in hay:
                continue
        out.append(resp)
    return out


def generate_payment_reference() -> str:
    return f"EISA-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:8].upper()}"


def audit_entry_dict(row: AuditLog, user: User | None = None) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "user_name": user.full_name if user else None,
        "action": row.action,
        "module": row.module,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "description": row.description,
        "old_value": row.old_value,
        "new_value": row.new_value,
        "ip_address": row.ip_address,
        "created_at": row.created_at,
    }


def snapshot_subscription(sub: OsgbSubscription) -> str:
    return json.dumps(
        {
            "status": sub.status.value,
            "package_id": sub.package_id,
            "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
            "current_period_ends_at": sub.current_period_ends_at.isoformat() if sub.current_period_ends_at else None,
            "is_auto_renew": sub.is_auto_renew,
        },
        ensure_ascii=False,
    )
