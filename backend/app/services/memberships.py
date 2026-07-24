"""P1-04 membership helpers — User.osgb_id/company_id ile geri uyumlu.

Membership satırı yoksa mevcut tek-alan modele düşer (davranış değişmez).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import OrganizationMembership, User, WorkplaceMembership


def active_osgb_ids_for_user(db: Session, user: User) -> list[int]:
    rows = db.scalars(
        select(OrganizationMembership.osgb_id).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active.is_(True),
        )
    ).all()
    ids = sorted({int(x) for x in rows if x is not None})
    if ids:
        return ids
    if user.osgb_id:
        return [int(user.osgb_id)]
    return []


def active_company_ids_for_user(db: Session, user: User) -> list[int]:
    rows = db.scalars(
        select(WorkplaceMembership.company_id).where(
            WorkplaceMembership.user_id == user.id,
            WorkplaceMembership.is_active.is_(True),
        )
    ).all()
    ids = sorted({int(x) for x in rows if x is not None})
    if ids:
        return ids
    if user.company_id:
        return [int(user.company_id)]
    return []


def user_has_osgb_membership(db: Session, user: User, osgb_id: int) -> bool:
    return int(osgb_id) in set(active_osgb_ids_for_user(db, user))


def user_has_company_membership(db: Session, user: User, company_id: int) -> bool:
    return int(company_id) in set(active_company_ids_for_user(db, user))
