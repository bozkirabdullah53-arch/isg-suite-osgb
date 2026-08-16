"""P1-04: Üyelik özeti + admin liste (iskelet)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    reject_company_bound_admin_from_osgb_internal,
    require_roles,
)
from app.api.tenant_access import (
    assert_can_manage_user,
    assert_company_in_admin_scope,
    accessible_company_ids_for_admin,
)
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
    wp_stmt = select(WorkplaceMembership).where(
        WorkplaceMembership.user_id == user.id,
        WorkplaceMembership.is_active.is_(True),
    )
    if user.role == UserRole.COMPANY_ADMIN and user.company_id is not None:
        # Eski/hatalı ek üyelikler tek-işyeri hesabının kendi özetini dahi
        # başka işyeri id'leriyle genişletmesin.
        wp_stmt = wp_stmt.where(WorkplaceMembership.company_id == user.company_id)
    wp_rows = list(db.scalars(wp_stmt).all())
    has_rows = bool(org_rows or wp_rows)
    if user.role == UserRole.COMPANY_ADMIN and user.company_id is not None:
        osgb_ids = [int(user.osgb_id)] if user.osgb_id is not None else []
        company_ids = [int(user.company_id)]
    else:
        osgb_ids = active_osgb_ids_for_user(db, user)
        company_ids = active_company_ids_for_user(db, user)
    return MembershipMeOut(
        osgb_ids=osgb_ids,
        company_ids=company_ids,
        organization_rows=len(org_rows),
        workplace_rows=len(wp_rows),
        source="membership_tables" if has_rows else "user_fields_fallback",
    )


@router.get("/organization", response_model=list[OrgMembershipOut])
def list_org_memberships(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    reject_company_bound_admin_from_osgb_internal(user)
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
    reject_company_bound_admin_from_osgb_internal(user)
    stmt = select(WorkplaceMembership).order_by(WorkplaceMembership.id.desc()).limit(200)
    if user.role != UserRole.GLOBAL_ADMIN:
        allowed = set(accessible_company_ids_for_admin(db, user))
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
    reject_company_bound_admin_from_osgb_internal(user)
    if user.role != UserRole.GLOBAL_ADMIN and user.osgb_id != payload.osgb_id:
        raise HTTPException(403, "Yalnızca kendi OSGB kapsamınıza üyelik ekleyebilirsiniz.")
    target = db.get(User, payload.user_id)
    if not target:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if user.role != UserRole.GLOBAL_ADMIN:
        assert_can_manage_user(db, user, target)
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
    reject_company_bound_admin_from_osgb_internal(user)
    if user.role != UserRole.GLOBAL_ADMIN:
        assert_company_in_admin_scope(db, user, payload.company_id)
    target = db.get(User, payload.user_id)
    if not target:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if user.role != UserRole.GLOBAL_ADMIN:
        assert_can_manage_user(db, user, target)
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
