"""Bireysel İSG uzmanı başvurularını İDEA Global onay kuyruğuna bağlar.

Mevcut OSGB başvuru API'sini değiştirmeden aynı Global ekranda bireysel uzman
başvurularını sentetik başvuru satırı olarak gösterir. Negatif başvuru kimliği
(``-user.id``) yalnız API/UI ayrımı içindir; gerçek veritabanı kimlikleri
değiştirilmez.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import auth as legacy_auth
from app.api import eisa as legacy_eisa
from app.api.deps import require_roles
from app.core.auth_cookies import clear_refresh_cookie
from app.core.database import get_db
from app.models.entities import (
    IsgProfessional,
    OsgbOrganization,
    OsgbSubscription,
    SubscriptionStatus,
    User,
    UserRole,
)
from app.schemas.auth import RegisterRequest, TokenResponse
from app.schemas.eisa_platform import OsgbApplicationApproveResponse
from app.schemas.osgb_subscription import OsgbApplicationReject, OsgbApplicationResponse
from app.services.audit import add_audit_log
from app.services.eisa_platform import build_dashboard, resolved_trial_days, subscription_response


auth_router = APIRouter(prefix="/auth", tags=["Kimlik Doğrulama"])
eisa_router = APIRouter(prefix="/eisa", tags=["EİSA Platform"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _individual_rows(db: Session) -> list[tuple[User, OsgbOrganization]]:
    return list(
        db.execute(
            select(User, OsgbOrganization)
            .join(OsgbOrganization, OsgbOrganization.id == User.osgb_id)
            .where(
                User.role == UserRole.SAFETY_SPECIALIST,
                OsgbOrganization.is_individual.is_(True),
            )
            .order_by(User.created_at.desc(), User.id.desc())
        ).all()
    )


def _status(user: User, org: OsgbOrganization) -> str:
    if org.archived_at is not None:
        return "rejected"
    return "approved" if bool(user.is_active) else "pending"


def _professional(db: Session, org_id: int) -> IsgProfessional | None:
    return db.scalar(
        select(IsgProfessional)
        .where(IsgProfessional.osgb_id == org_id)
        .order_by(IsgProfessional.id)
        .limit(1)
    )


def _as_application(db: Session, user: User, org: OsgbOrganization) -> OsgbApplicationResponse:
    professional = _professional(db, org.id)
    cert_class = (professional.certificate_class or "—") if professional else "—"
    cert_no = (professional.certificate_number or "—") if professional else "—"
    state = _status(user, org)
    return OsgbApplicationResponse(
        id=-int(user.id),
        name=f"Bireysel Uzman — {user.full_name}",
        authorization_number=f"{cert_class} / {cert_no}",
        tax_number="BİREYSEL",
        responsible_manager=user.full_name,
        contact_email=user.email,
        contact_phone=professional.phone if professional else org.phone,
        address=org.address,
        applicant_name=user.full_name,
        applicant_email=user.email,
        notes="İş Güvenliği Uzmanı bireysel üyelik başvurusu",
        status=state,
        matched_osgb_id=org.id,
        auto_matched=False,
        rejection_reason=("EİSA Global tarafından reddedildi." if state == "rejected" else None),
        created_at=user.created_at or org.created_at,
        reviewed_at=org.archived_at if state == "rejected" else None,
    )


def _get_individual(db: Session, synthetic_id: int) -> tuple[User, OsgbOrganization]:
    if synthetic_id >= 0:
        raise HTTPException(404, "Bireysel uzman başvurusu bulunamadı.")
    user = db.get(User, -synthetic_id)
    if not user or user.role != UserRole.SAFETY_SPECIALIST or not user.osgb_id:
        raise HTTPException(404, "Bireysel uzman başvurusu bulunamadı.")
    org = db.get(OsgbOrganization, user.osgb_id)
    if not org or not bool(org.is_individual):
        raise HTTPException(404, "Bireysel uzman başvurusu bulunamadı.")
    return user, org


def _set_professionals_active(db: Session, org_id: int, active: bool) -> None:
    rows = list(db.scalars(select(IsgProfessional).where(IsgProfessional.osgb_id == org_id)).all())
    for row in rows:
        row.is_active = active


def _subscription(db: Session, org_id: int) -> OsgbSubscription | None:
    return db.scalar(select(OsgbSubscription).where(OsgbSubscription.osgb_id == org_id).limit(1))


@auth_router.post("/register", response_model=TokenResponse, status_code=201)
def register_pending_specialist(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Bireysel uzman kaydını oluşturur fakat Global onayından önce token vermez."""
    body = legacy_auth.register(payload=payload, request=request, response=response, db=db)
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email).limit(1))
    org = db.get(OsgbOrganization, user.osgb_id) if user and user.osgb_id else None
    if user and org and bool(org.is_individual) and user.role == UserRole.SAFETY_SPECIALIST:
        # before_insert güvenlik kuralı hesabı pasif bırakır. Eski auth.register
        # token üretse dahi onu tarayıcıya vermeyiz ve refresh cookie'yi temizleriz.
        clear_refresh_cookie(response)
        return TokenResponse()
    return body


@eisa_router.get("/dashboard")
def dashboard_with_individual_applications(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    data = dict(build_dashboard(db))
    individual_pending = sum(1 for user, org in _individual_rows(db) if _status(user, org) == "pending")
    data["pending_applications"] = int(data.get("pending_applications") or 0) + individual_pending
    return data


@eisa_router.get("/applications", response_model=list[OsgbApplicationResponse])
def list_applications_with_individuals(
    status: str | None = "pending",
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    # Gerçek OSGB başvurularının mevcut davranışını aynen koru.
    real_rows = legacy_eisa.list_applications(status=status, db=db, _=admin)
    out = [OsgbApplicationResponse.model_validate(row) for row in real_rows]

    wanted = (status or "all").strip().lower()
    for user, org in _individual_rows(db):
        row = _as_application(db, user, org)
        if wanted not in ("all", "*") and row.status != wanted:
            continue
        out.append(row)

    out.sort(key=lambda row: row.created_at, reverse=True)
    return out


@eisa_router.get("/individual-subscriptions")
def list_individual_subscriptions(
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Onaylanmış bireysel İSG uzmanı aboneliklerini OSGB aboneliklerinden ayrı listeler."""
    needle = (q or "").strip().lower()
    out: list[dict] = []
    for user, org in _individual_rows(db):
        if _status(user, org) != "approved":
            continue
        sub = _subscription(db, org.id)
        if not sub:
            continue
        professional = _professional(db, org.id)
        row = subscription_response(db, sub).model_dump()
        row.update(
            {
                "user_id": user.id,
                "osgb_name": user.full_name,
                "specialist_name": user.full_name,
                "specialist_email": user.email,
                "specialist_phone": professional.phone if professional else org.phone,
                "certificate_class": professional.certificate_class if professional else None,
                "certificate_number": professional.certificate_number if professional else None,
            }
        )
        if needle:
            hay = " ".join(
                str(value or "")
                for value in (
                    row.get("specialist_name"),
                    row.get("specialist_email"),
                    row.get("specialist_phone"),
                    row.get("certificate_class"),
                    row.get("certificate_number"),
                    row.get("package_name"),
                )
            ).lower()
            if needle not in hay:
                continue
        out.append(row)
    out.sort(key=lambda row: str(row.get("specialist_name") or "").lower())
    return out


@eisa_router.post("/applications/{application_id}/approve", response_model=OsgbApplicationApproveResponse)
def approve_application_with_individuals(
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    if application_id >= 0:
        return legacy_eisa.approve(application_id=application_id, request=request, db=db, user=admin)

    user, org = _get_individual(db, application_id)
    if org.archived_at is not None:
        raise HTTPException(400, "Bu bireysel uzman başvurusu reddedilmiş. Önce yeni başvuru gerekir.")
    if user.is_active:
        return OsgbApplicationApproveResponse(application=_as_application(db, user, org), admin_account=None)

    now = datetime.utcnow()
    user.is_active = True
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    org.is_active = True
    org.archived_at = None
    _set_professionals_active(db, org.id, True)

    sub = _subscription(db, org.id)
    if sub:
        # Ücretsiz deneme başvuru anında değil, Global onay anında başlar.
        sub.status = SubscriptionStatus.TRIAL
        sub.trial_ends_at = now + timedelta(days=resolved_trial_days(db))
        sub.updated_at = now

    add_audit_log(
        db,
        user=admin,
        action="individual_specialist_application_approved",
        module="eisa",
        entity_type="user",
        entity_id=str(user.id),
        description=f"Bireysel İSG uzmanı başvurusu onaylandı: {user.email}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(user)
    db.refresh(org)
    return OsgbApplicationApproveResponse(application=_as_application(db, user, org), admin_account=None)


@eisa_router.post("/applications/{application_id}/reject", response_model=OsgbApplicationResponse)
def reject_application_with_individuals(
    application_id: int,
    payload: OsgbApplicationReject,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    if application_id >= 0:
        return legacy_eisa.reject(
            application_id=application_id,
            payload=payload,
            request=request,
            db=db,
            user=admin,
        )

    user, org = _get_individual(db, application_id)
    if user.is_active:
        raise HTTPException(400, "Onaylanmış bireysel uzman başvurusu bu ekrandan reddedilemez.")
    if org.archived_at is not None:
        return _as_application(db, user, org)

    now = datetime.utcnow()
    user.is_active = False
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    org.is_active = False
    org.archived_at = now
    _set_professionals_active(db, org.id, False)
    sub = _subscription(db, org.id)
    if sub:
        sub.status = SubscriptionStatus.SUSPENDED
        sub.updated_at = now

    add_audit_log(
        db,
        user=admin,
        action="individual_specialist_application_rejected",
        module="eisa",
        entity_type="user",
        entity_id=str(user.id),
        description=f"Bireysel İSG uzmanı başvurusu reddedildi: {user.email}. Gerekçe: {payload.reason.strip()}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(user)
    db.refresh(org)
    return _as_application(db, user, org)


@eisa_router.delete("/applications/{application_id}")
def delete_application_with_individuals(
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    if application_id >= 0:
        return legacy_eisa.delete_application(
            application_id=application_id,
            request=request,
            db=db,
            user=admin,
        )

    # Bireysel başvurularda fiziksel veri silmeyiz. Kullanıcı/tenant izolasyonunu
    # korumak için satırı arşivleyerek Global listesinden pending filtresinde çıkarırız.
    user, org = _get_individual(db, application_id)
    now = datetime.utcnow()
    user.is_active = False
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    org.is_active = False
    org.archived_at = org.archived_at or now
    _set_professionals_active(db, org.id, False)
    sub = _subscription(db, org.id)
    if sub:
        sub.status = SubscriptionStatus.SUSPENDED
        sub.updated_at = now
    add_audit_log(
        db,
        user=admin,
        action="individual_specialist_application_archived",
        module="eisa",
        entity_type="user",
        entity_id=str(user.id),
        description=f"Bireysel uzman başvuru satırı arşivlendi: {user.email}",
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"ok": True, "id": application_id, "message": "Bireysel uzman başvurusu arşivlendi."}
