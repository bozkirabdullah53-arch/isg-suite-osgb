"""Read-only endpoints for the premium Education action dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.company_access import effective_company_id, ensure_company_access
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.services.training_premium_dashboard_v1 import build_dashboard, dashboard_active

router = APIRouter(prefix="/trainings", tags=["Eğitim Premium Dashboard"])


@router.get("/premium-dashboard")
def premium_training_dashboard(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    effective = effective_company_id(db, user, company_id)
    ensure_company_access(db, user, effective)
    if not dashboard_active():
        return {
            "enabled": False,
            "company_id": effective,
            "actions": [],
            "rows": [],
            "summary": {},
            "safety": {"read_only": True},
        }
    return build_dashboard(db, company_id=effective)
