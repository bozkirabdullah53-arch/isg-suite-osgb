"""Read-only audit endpoints for exact-NACE exam question selection."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import TrainingSession, User, UserRole
from app.services.training_question_selection_v2 import question_selection_audit

router = APIRouter(prefix="/trainings", tags=["Eğitim Sınav Seçim Denetimi"])
AUDIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
)


@router.get("/{training_id}/exam-selection-audit")
def exam_selection_audit(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*AUDIT_ROLES)),
):
    """Compare legacy alias fallback with verified exact-NACE selection.

    This endpoint is read-only. It does not create an exam, mutate the question
    bank, or enable the strict feature flag.
    """
    training = db.get(TrainingSession, training_id)
    if training is None:
        raise HTTPException(404, "Eğitim kaydı bulunamadı.")
    ensure_company_access(db, user, training.company_id)
    return question_selection_audit(db, training)
