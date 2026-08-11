"""Kullanıcının gerçek OSGB / işyeri kapsamını doğrular."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    Company,
    IsgProfessional,
    OrganizationMembership,
    OsgbOrganization,
    ProfessionalType,
    User,
    UserRole,
    WorkplaceMembership,
)

_FIELD_ROLE_TO_TYPE = {
    UserRole.SAFETY_SPECIALIST: ProfessionalType.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN: ProfessionalType.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL: ProfessionalType.OTHER_HEALTH_PERSONNEL,
}


def _active_osgb(db: Session, osgb_id: int | None) -> OsgbOrganization | None:
    if not osgb_id:
        return None
    row = db.get(OsgbOrganization, osgb_id)
    return row if row and row.is_active else None


def _active_company(db: Session, company_id: int | None) -> Company | None:
    if not company_id:
        return None
    row = db.get(Company, company_id)
    return row if row and row.is_active else None


def _active_org_membership(db: Session, user_id: int) -> OrganizationMembership | None:
    return db.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.is_active.is_(True),
        )
        .order_by(OrganizationMembership.id)
        .limit(1)
    )


def _active_workplace_membership(db: Session, user_id: int) -> WorkplaceMembership | None:
    return db.scalar(
        select(WorkplaceMembership)
        .where(
            WorkplaceMembership.user_id == user_id,
            WorkplaceMembership.is_active.is_(True),
        )
        .order_by(WorkplaceMembership.id)
        .limit(1)
    )


def _professional_for_user(db: Session, user: User) -> IsgProfessional | None:
    expected_type = _FIELD_ROLE_TO_TYPE.get(user.role)
    if expected_type is None:
        return None
    email = (user.email or "").strip().lower()
    if not email:
        return None
    return db.scalar(
        select(IsgProfessional)
        .where(
            func.lower(IsgProfessional.email) == email,
            IsgProfessional.professional_type == expected_type,
            IsgProfessional.is_active.is_(True),
        )
        .order_by(IsgProfessional.id)
        .limit(1)
    )


def ensure_login_scope(db: Session, user: User) -> User:
    if user.role == UserRole.GLOBAL_ADMIN:
        return user

    if user.role == UserRole.COMPANY_ADMIN:
        company = _active_company(db, user.company_id)
        if company:
            if company.osgb_id and user.osgb_id != company.osgb_id:
                user.osgb_id = company.osgb_id
                db.flush()
            return user

        osgb = _active_osgb(db, user.osgb_id)
        if osgb:
            return user

        membership = _active_org_membership(db, user.id)
        if membership and _active_osgb(db, membership.osgb_id):
            if user.osgb_id != membership.osgb_id:
                user.osgb_id = membership.osgb_id
                db.flush()
            return user

        workplace = _active_workplace_membership(db, user.id)
        if workplace and _active_company(db, workplace.company_id):
            if user.company_id != workplace.company_id:
                user.company_id = workplace.company_id
                db.flush()
            return user

        raise HTTPException(
            403,
            "Bu yönetici hesabı herhangi bir OSGB veya işyerine bağlı değil. "
            "Global yöneticiden kurum bağlantısını düzeltmesini isteyin.",
        )

    # İş güvenliği uzmanı, mevcut tek-firma hesaplarında company_id / OSGB
    # kapsamıyla oturum açmaya devam edebilir; bu geriye dönük uyumluluk,
    # uzman odasının eski kullanıcılarını kilitlemez. Klinik roller ise
    # aşağıdaki sıkı profesyonel eşleşmesine tabidir.
    if user.role == UserRole.SAFETY_SPECIALIST:
        professional = _professional_for_user(db, user)
        if professional:
            osgb = _active_osgb(db, professional.osgb_id)
            if not osgb:
                raise HTTPException(403, "İSG profesyoneli kaydı aktif bir OSGB'ye bağlı değil.")
            if user.osgb_id != professional.osgb_id:
                user.osgb_id = professional.osgb_id
                db.flush()
            return user
        company = _active_company(db, user.company_id)
        if company:
            if company.osgb_id and user.osgb_id != company.osgb_id:
                user.osgb_id = company.osgb_id
                db.flush()
            return user
        osgb = _active_osgb(db, user.osgb_id)
        if osgb:
            return user
        raise HTTPException(
            403,
            "Bu uzman hesabı aktif bir OSGB veya işyerine bağlı değil. "
            "Görevlendirme / kurum bağlantısını düzeltin.",
        )

    if user.role in (UserRole.WORKPLACE_PHYSICIAN, UserRole.OTHER_HEALTH_PERSONNEL):
        professional = _professional_for_user(db, user)
        if not professional:
            raise HTTPException(
                403,
                "Bu mesleki kullanıcı hesabının aktif İSG profesyoneli kaydı bulunamadı. "
                "Önce OSGB içinden profesyonel kaydı oluşturulmalı ve aynı e-posta kullanılmalıdır.",
            )

        osgb = _active_osgb(db, professional.osgb_id)
        if not osgb:
            raise HTTPException(403, "İSG profesyoneli kaydı aktif bir OSGB'ye bağlı değil.")

        if user.osgb_id != professional.osgb_id:
            user.osgb_id = professional.osgb_id
            db.flush()
        return user

    if user.role == UserRole.READ_ONLY:
        if _active_company(db, user.company_id) or _active_osgb(db, user.osgb_id):
            return user
        if _active_org_membership(db, user.id) or _active_workplace_membership(db, user.id):
            return user
        raise HTTPException(403, "Bu kullanıcı herhangi bir kurum veya işyerine bağlı değil.")

    raise HTTPException(403, "Kullanıcı rolü için geçerli erişim kapsamı bulunamadı.")
