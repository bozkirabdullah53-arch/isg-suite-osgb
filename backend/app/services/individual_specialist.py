"""Bireysel İSG uzmanı çalışma alanı — gerçek OSGB ile karışmaz."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentStatus,
    Company,
    IsgProfessional,
    OsgbOrganization,
    OsgbSubscription,
    OsgbSubscriptionPlan,
    ProfessionalType,
    SubscriptionStatus,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.services.eisa_platform import resolved_trial_days


def is_individual_org(org: OsgbOrganization | None) -> bool:
    return bool(org is not None and getattr(org, "is_individual", False))


def is_individual_specialist(db: Session, user: User | None) -> bool:
    if user is None or user.role != UserRole.SAFETY_SPECIALIST or not user.osgb_id:
        return False
    return is_individual_org(db.get(OsgbOrganization, user.osgb_id))


@event.listens_for(User, "before_insert", propagate=True)
def require_global_approval_for_individual_specialist(_mapper, connection, target: User) -> None:
    """Yeni bireysel uzman hesabını Global onayına kadar pasif oluştur.

    Yalnız ``is_individual`` çalışma alanına bağlı İSG uzmanlarını etkiler;
    normal OSGB kullanıcılarının mevcut oluşturma akışına dokunmaz.
    """
    if target.role != UserRole.SAFETY_SPECIALIST or not target.osgb_id:
        return
    is_individual = connection.execute(
        select(OsgbOrganization.is_individual).where(OsgbOrganization.id == target.osgb_id)
    ).scalar_one_or_none()
    if bool(is_individual):
        target.is_active = False


def provision_individual_workspace(
    db: Session,
    *,
    full_name: str,
    email: str,
    phone: str | None,
    certificate_class: str | None,
    certificate_number: str,
) -> tuple[OsgbOrganization, IsgProfessional, OsgbSubscription]:
    """Create an isolated workspace without relying on a person's name for uniqueness."""
    now = datetime.utcnow()
    trial_days = resolved_trial_days(db)
    workspace_token = uuid4().hex[:12].upper()
    workspace = OsgbOrganization(
        name=f"{full_name} — Bireysel Uzman — {workspace_token}"[:220],
        authorization_number=f"IND-{workspace_token}",
        email=email,
        phone=(phone or "").strip() or None,
        responsible_manager=full_name,
        is_active=True,
        is_individual=True,
    )
    try:
        db.add(workspace)
        db.flush()
        professional = IsgProfessional(
            osgb_id=workspace.id,
            full_name=full_name,
            email=email,
            phone=(phone or "").strip() or None,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class=certificate_class,
            certificate_number=certificate_number,
            is_active=True,
        )
        subscription = OsgbSubscription(
            osgb_id=workspace.id,
            plan=OsgbSubscriptionPlan.STANDARD,
            status=SubscriptionStatus.TRIAL,
            trial_ends_at=now + timedelta(days=trial_days),
            max_users=1,
            max_workplaces=3,
        )
        db.add_all([professional, subscription])
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Bu e-posta veya sertifika numarası zaten kayıtlı.") from exc
    return workspace, professional, subscription


def ensure_individual_workplace_assignment(
    db: Session,
    user: User,
    company: Company,
) -> WorkplaceAssignment | None:
    """Bireysel uzman kendi işyerini açınca aktif görevlendirme satırı da oluşur."""
    if not is_individual_specialist(db, user) or company is None:
        return None
    pro = db.scalar(
        select(IsgProfessional)
        .where(
            IsgProfessional.osgb_id == user.osgb_id,
            IsgProfessional.professional_type == ProfessionalType.SAFETY_SPECIALIST,
            IsgProfessional.is_active.is_(True),
        )
        .order_by(IsgProfessional.id)
        .limit(1)
    )
    if not pro:
        return None
    existing = db.scalar(
        select(WorkplaceAssignment).where(
            WorkplaceAssignment.company_id == company.id,
            WorkplaceAssignment.professional_id == pro.id,
            WorkplaceAssignment.professional_type == ProfessionalType.SAFETY_SPECIALIST,
        ).limit(1)
    )
    if existing:
        if existing.status != AssignmentStatus.ACTIVE:
            existing.status = AssignmentStatus.ACTIVE
            existing.end_date = None
            db.flush()
        return existing
    obj = WorkplaceAssignment(
        osgb_id=int(user.osgb_id),
        company_id=company.id,
        professional_id=pro.id,
        professional_type=ProfessionalType.SAFETY_SPECIALIST,
        start_date=date.today(),
        required_minutes_monthly=0,
        planned_minutes_monthly=0,
        actual_minutes_monthly=0,
        status=AssignmentStatus.ACTIVE,
    )
    db.add(obj)
    db.flush()
    return obj
