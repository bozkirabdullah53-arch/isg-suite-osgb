"""P1-04: Üyelik özeti + admin liste (iskelet)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import (
    OrganizationMembership,
    User,
    UserRole,
    WorkplaceMembership,
)
from app.services.memberships import active_company_ids_for_user, active_osgb_ids_for_user

router = APIRouter(prefix="/memberships", tags=["Üyelikler"])


class MembershipMeOut(BaseModel):
    osgb_ids: list[int]
    company_ids: list[int]
    organization_rows: int
    workplace_rows: int
    source: str


class OrgMembershipOut(BaseModel):
    id: int
    user_id: int
    osgb_id: int
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WpMembershipOut(BaseModel):
    id: int
    user_id: int
    company_id: int
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateOrgMembership(BaseModel):
    user_id: int
    osgb_id: int
    role: str = Field(default="company_admin", max_length=40)


class CreateWpMembership(BaseModel):
    user_id: int
    company_id: int
    role: str = Field(default="read_only", max_length=40)


@router.get("/me", response_model=MembershipMeOut)
def my_memberships(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org_rows = list(
        db.scalars(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.is_active.is_(True),
            )
        ).all()
    )
    wp_rows = list(
        db.scalars(
            select(WorkplaceMembership).where(
                WorkplaceMembership.user_id == user.id,
                WorkplaceMembership.is_active.is_(True),
            )
        ).all()
    )
    has_rows = bool(org_rows or wp_rows)
    return MembershipMeOut(
        osgb_ids=active_osgb_ids_for_user(db, user),
        company_ids=active_company_ids_for_user(db, user),
        organization_rows=len(org_rows),
        workplace_rows=len(wp_rows),
        source="membership_tables" if has_rows else "user_fields_fallback",
    )


@router.get("/organization", response_model=list[OrgMembershipOut])
def list_org_memberships(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    stmt = select(OrganizationMembership).order_by(OrganizationMembership.id.desc()).limit(200)
    if user.role != UserRole.GLOBAL_ADMIN:
        if not user.osgb_id:
            return []
        stmt = stmt.where(OrganizationMembership.osgb_id == user.osgb_id)
    return list(db.scalars(stmt).all())


@router.get("/workplace", response_model=list[WpMembershipOut])
def list_wp_memberships(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    stmt = select(WorkplaceMembership).order_by(WorkplaceMembership.id.desc()).limit(200)
    if user.role != UserRole.GLOBAL_ADMIN:
        allowed = set(active_company_ids_for_user(db, user))
        if user.osgb_id and not allowed:
            from app.models.entities import Company

            allowed = set(db.scalars(select(Company.id).where(Company.osgb_id == user.osgb_id)).all())
        if not allowed:
            return []
        stmt = stmt.where(WorkplaceMembership.company_id.in_(allowed))
    return list(db.scalars(stmt).all())


@router.post("/organization", response_model=OrgMembershipOut)
def create_org_membership(
    payload: CreateOrgMembership,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    if user.role != UserRole.GLOBAL_ADMIN and user.osgb_id != payload.osgb_id:
        raise HTTPException(403, "Yalnızca kendi OSGB kapsamınıza üyelik ekleyebilirsiniz.")
    target = db.get(User, payload.user_id)
    if not target:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    existing = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == payload.user_id,
            OrganizationMembership.osgb_id == payload.osgb_id,
            OrganizationMembership.role == payload.role,
        )
    )
    if existing:
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing
    row = OrganizationMembership(
        user_id=payload.user_id,
        osgb_id=payload.osgb_id,
        role=payload.role.strip() or "company_admin",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/workplace", response_model=WpMembershipOut)
def create_wp_membership(
    payload: CreateWpMembership,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    if user.role != UserRole.GLOBAL_ADMIN:
        allowed = set(active_company_ids_for_user(db, user))
        if payload.company_id not in allowed and user.company_id != payload.company_id:
            from app.models.entities import Company

            co = db.get(Company, payload.company_id)
            if not co or co.osgb_id != user.osgb_id:
                raise HTTPException(403, "Bu işyerine üyelik ekleyemezsiniz.")
    target = db.get(User, payload.user_id)
    if not target:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    existing = db.scalar(
        select(WorkplaceMembership).where(
            WorkplaceMembership.user_id == payload.user_id,
            WorkplaceMembership.company_id == payload.company_id,
            WorkplaceMembership.role == payload.role,
        )
    )
    if existing:
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing
    row = WorkplaceMembership(
        user_id=payload.user_id,
        company_id=payload.company_id,
        role=payload.role.strip() or "read_only",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
