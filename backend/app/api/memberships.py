"""P1-04: Kullanıcının OSGB / işyeri üyelik özeti (iskelet)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import OrganizationMembership, User, WorkplaceMembership
from app.services.memberships import active_company_ids_for_user, active_osgb_ids_for_user

router = APIRouter(prefix="/memberships", tags=["Üyelikler"])


class MembershipMeOut(BaseModel):
    osgb_ids: list[int]
    company_ids: list[int]
    organization_rows: int
    workplace_rows: int
    source: str  # "membership_tables" | "user_fields_fallback"


@router.get("/me", response_model=MembershipMeOut)
def my_memberships(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org_n = db.scalar(
        select(OrganizationMembership.id)
        .where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active.is_(True),
        )
        .limit(1)
    )
    wp_n = db.scalar(
        select(WorkplaceMembership.id)
        .where(
            WorkplaceMembership.user_id == user.id,
            WorkplaceMembership.is_active.is_(True),
        )
        .limit(1)
    )
    has_rows = org_n is not None or wp_n is not None
    org_count = len(
        db.scalars(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.is_active.is_(True),
            )
        ).all()
    )
    wp_count = len(
        db.scalars(
            select(WorkplaceMembership).where(
                WorkplaceMembership.user_id == user.id,
                WorkplaceMembership.is_active.is_(True),
            )
        ).all()
    )
    return MembershipMeOut(
        osgb_ids=active_osgb_ids_for_user(db, user),
        company_ids=active_company_ids_for_user(db, user),
        organization_rows=org_count,
        workplace_rows=wp_count,
        source="membership_tables" if has_rows else "user_fields_fallback",
    )
