"""Tenant / OSGB izolasyon yardımcıları.

Kural: company_id IS NULL eşleşmesi asla tenant kanıtı sayılmaz.
OSGB admin (company_admin + osgb_id) yalnızca kendi OSGB kapsamındaki
kullanıcı / firma / kayıtları görür.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.models.entities import Company, User, UserRole


def company_ids_for_osgb(db: Session, osgb_id: int) -> list[int]:
    return list(db.scalars(select(Company.id).where(Company.osgb_id == osgb_id)).all())


def accessible_company_ids_for_admin(db: Session, user: User) -> list[int]:
    """company_admin için erişilebilir işyeri id listesi."""
    if user.role == UserRole.GLOBAL_ADMIN:
        return []
    if user.role != UserRole.COMPANY_ADMIN:
        return [user.company_id] if user.company_id else []
    if user.company_id:
        return [user.company_id]
    if user.osgb_id:
        return company_ids_for_osgb(db, user.osgb_id)
    return []


def user_in_admin_scope(db: Session, current: User, target: User) -> bool:
    """current, target kullanıcısını yönetebilir mi?"""
    if current.role == UserRole.GLOBAL_ADMIN:
        return True
    if current.role != UserRole.COMPANY_ADMIN:
        return False
    if target.role == UserRole.GLOBAL_ADMIN:
        return False

    if current.osgb_id:
        if target.osgb_id == current.osgb_id:
            return True
        if target.company_id:
            company = db.get(Company, target.company_id)
            if company and company.osgb_id == current.osgb_id:
                return True
        return False

    # Yalnızca company_id ile bağlı firma admini — NULL eşleşmesi yasak
    if current.company_id is None:
        return False
    return target.company_id == current.company_id


def assert_can_manage_user(db: Session, current: User, target: User) -> None:
    if not user_in_admin_scope(db, current, target):
        raise HTTPException(403, "Bu kullanıcıya erişemezsiniz.")


def users_scope_filter(db: Session, current: User) -> ColumnElement | None:
    """User listesi için SQL filtresi. None = global (filtre yok)."""
    if current.role == UserRole.GLOBAL_ADMIN:
        return None
    if current.role != UserRole.COMPANY_ADMIN:
        raise HTTPException(403, "Yetkisiz.")

    if current.osgb_id:
        company_ids = company_ids_for_osgb(db, current.osgb_id)
        parts = [User.osgb_id == current.osgb_id]
        if company_ids:
            parts.append(User.company_id.in_(company_ids))
        return or_(*parts)

    if current.company_id is not None:
        return User.company_id == current.company_id

    # Ne osgb ne company — hiçbir kullanıcıyı görme
    return User.id == -1


def assert_company_in_admin_scope(db: Session, current: User, company_id: int | None) -> None:
    if current.role == UserRole.GLOBAL_ADMIN:
        return
    if company_id is None:
        return
    allowed = accessible_company_ids_for_admin(db, current)
    if company_id not in allowed:
        raise HTTPException(403, "Bu firmaya kullanıcı bağlayamazsınız.")
