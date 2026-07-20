"""OSGB merkez yöneticisi hesabı oluşturma ve şifre atama."""
from __future__ import annotations

import secrets
import string

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.entities import OsgbApplication, OsgbOrganization, User, UserRole


def generate_temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
        ):
            return pwd


def find_osgb_admin(db: Session, osgb_id: int) -> User | None:
    return db.scalar(
        select(User)
        .where(
            User.osgb_id == osgb_id,
            User.role == UserRole.COMPANY_ADMIN,
            User.is_active.is_(True),
        )
        .order_by(User.id)
        .limit(1)
    )


def provision_osgb_admin(
    db: Session,
    osgb: OsgbOrganization,
    *,
    email: str,
    full_name: str,
    application: OsgbApplication | None = None,
) -> tuple[User, str, bool]:
    """OSGB yönetici hesabı oluştur veya mevcut hesaba geçici şifre ata."""
    email = email.strip().lower()
    if not email:
        raise HTTPException(422, "Yönetici e-posta adresi gerekli.")
    name = (full_name or osgb.responsible_manager or osgb.name).strip()
    if len(name) < 2:
        raise HTTPException(422, "Yönetici adı gerekli.")

    temp_password = generate_temporary_password()
    user = db.scalar(select(User).where(User.email == email))
    created = False

    if user:
        if user.role == UserRole.GLOBAL_ADMIN:
            raise HTTPException(409, "Bu e-posta EİSA global yönetici hesabına ait.")
        user.full_name = name
        user.role = UserRole.COMPANY_ADMIN
        user.osgb_id = osgb.id
        user.is_active = True
        user.hashed_password = get_password_hash(temp_password)
    else:
        user = User(
            email=email,
            full_name=name,
            hashed_password=get_password_hash(temp_password),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            company_id=None,
            is_active=True,
        )
        db.add(user)
        created = True

    if application:
        application.matched_osgb_id = osgb.id

    db.flush()
    return user, temp_password, created


def provision_from_application(db: Session, application: OsgbApplication, osgb: OsgbOrganization) -> tuple[User, str, bool] | None:
    email = (application.applicant_email or application.contact_email or "").strip().lower()
    if not email:
        return None
    return provision_osgb_admin(
        db,
        osgb,
        email=email,
        full_name=application.applicant_name or application.responsible_manager or osgb.name,
        application=application,
    )
