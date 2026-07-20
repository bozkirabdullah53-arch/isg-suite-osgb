"""OSGB abonelik ve başvuru iş kuralları (EİSA platform)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    OsgbApplication,
    OsgbApplicationStatus,
    OsgbOrganization,
    OsgbSubscription,
    OsgbSubscriptionPlan,
    SubscriptionStatus,
    User,
    UserRole,
)

TRIAL_DAYS = 10
WRITE_STATUSES = frozenset({SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE})


def normalize_id(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[\s\-\./]", "", str(value).strip().upper())


def find_osgb_by_credentials(
    db: Session, *, authorization_number: str, tax_number: str
) -> OsgbOrganization | None:
    auth = normalize_id(authorization_number)
    tax = normalize_id(tax_number)
    if auth:
        row = db.scalar(
            select(OsgbOrganization).where(OsgbOrganization.authorization_number == authorization_number.strip())
        )
        if row:
            return row
        for org in db.scalars(select(OsgbOrganization)).all():
            if normalize_id(org.authorization_number) == auth:
                return org
    if tax:
        matches = [
            o
            for o in db.scalars(select(OsgbOrganization)).all()
            if normalize_id(o.tax_number) == tax
        ]
        if len(matches) == 1:
            return matches[0]
    return None


def get_or_create_subscription(db: Session, osgb_id: int) -> OsgbSubscription:
    sub = db.scalar(select(OsgbSubscription).where(OsgbSubscription.osgb_id == osgb_id))
    if sub:
        return sub
    now = datetime.utcnow()
    sub = OsgbSubscription(
        osgb_id=osgb_id,
        plan=OsgbSubscriptionPlan.STANDARD,
        status=SubscriptionStatus.TRIAL,
        trial_ends_at=now + timedelta(days=TRIAL_DAYS),
        max_users=50,
        max_workplaces=100,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def effective_subscription_status(sub: OsgbSubscription, now: datetime | None = None) -> SubscriptionStatus:
    now = now or datetime.utcnow()
    if sub.status in (SubscriptionStatus.SUSPENDED, SubscriptionStatus.CANCELLED):
        return sub.status
    if sub.status == SubscriptionStatus.TRIAL:
        if sub.trial_ends_at and sub.trial_ends_at < now:
            return SubscriptionStatus.PAST_DUE
        return SubscriptionStatus.TRIAL
    if sub.status == SubscriptionStatus.ACTIVE:
        if sub.current_period_ends_at and sub.current_period_ends_at < now:
            return SubscriptionStatus.PAST_DUE
        return SubscriptionStatus.ACTIVE
    return sub.status


def subscription_allows_write(sub: OsgbSubscription | None, now: datetime | None = None) -> bool:
    if not sub:
        return False
    return effective_subscription_status(sub, now) in WRITE_STATUSES


def resolve_user_osgb_id(db: Session, user: User) -> int | None:
    if user.osgb_id:
        return user.osgb_id
    if user.company_id:
        from app.models.entities import Company

        company = db.get(Company, user.company_id)
        if company and company.osgb_id:
            return company.osgb_id
    if user.role in (
        UserRole.SAFETY_SPECIALIST,
        UserRole.WORKPLACE_PHYSICIAN,
        UserRole.OTHER_HEALTH_PERSONNEL,
    ):
        from app.api.company_access import find_professional_for_user

        pro = find_professional_for_user(db, user)
        if pro:
            return pro.osgb_id
    return None


def assert_osgb_write_access(db: Session, user: User, osgb_id: int | None = None) -> None:
    if user.role == UserRole.GLOBAL_ADMIN:
        return
    oid = osgb_id or resolve_user_osgb_id(db, user)
    if not oid:
        raise HTTPException(403, "OSGB kapsamı belirlenemedi.")
    sub = get_or_create_subscription(db, oid)
    if not subscription_allows_write(sub):
        raise HTTPException(
            403,
            "Abonelik süresi doldu veya askıda. Veri girişi kapalı — salt okunur moddasınız. "
            "EİSA ile iletişime geçin.",
        )


def approve_application(db: Session, application: OsgbApplication, reviewer: User) -> OsgbOrganization:
    if application.status != OsgbApplicationStatus.PENDING:
        raise HTTPException(400, "Başvuru zaten işlenmiş.")
    matched = find_osgb_by_credentials(
        db,
        authorization_number=application.authorization_number,
        tax_number=application.tax_number,
    )
    if matched:
        osgb = matched
        application.auto_matched = True
        osgb.name = application.name.strip()
        osgb.authorization_number = application.authorization_number.strip()
        osgb.tax_number = application.tax_number.strip()
        osgb.responsible_manager = application.responsible_manager
        osgb.email = application.contact_email
        osgb.phone = application.contact_phone
        osgb.address = application.address
        osgb.is_active = True
    else:
        osgb = OsgbOrganization(
            name=application.name.strip(),
            authorization_number=application.authorization_number.strip(),
            tax_number=application.tax_number.strip(),
            responsible_manager=application.responsible_manager,
            email=application.contact_email,
            phone=application.contact_phone,
            address=application.address,
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        application.auto_matched = False

    now = datetime.utcnow()
    sub = db.scalar(select(OsgbSubscription).where(OsgbSubscription.osgb_id == osgb.id))
    if not sub:
        sub = OsgbSubscription(
            osgb_id=osgb.id,
            plan=OsgbSubscriptionPlan.STANDARD,
            status=SubscriptionStatus.TRIAL,
            trial_ends_at=now + timedelta(days=TRIAL_DAYS),
            max_users=50,
            max_workplaces=100,
        )
        db.add(sub)
    else:
        sub.status = SubscriptionStatus.TRIAL
        sub.trial_ends_at = now + timedelta(days=TRIAL_DAYS)
        sub.plan = OsgbSubscriptionPlan.STANDARD

    application.status = OsgbApplicationStatus.APPROVED
    application.matched_osgb_id = osgb.id
    application.reviewed_by_user_id = reviewer.id
    application.reviewed_at = now
    db.commit()
    db.refresh(osgb)
    return osgb
