"""Optional NACE training presentation API — Phase 1 read-only boundary."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import TrainingSession, User
from app.services.training_presentation_readiness import training_presentation_readiness

router = APIRouter(prefix="/trainings", tags=["NACE Eğitim Sunumu"])


@router.get("/{training_id}/presentation-readiness")
def presentation_readiness(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return readiness without mutating training, exam, certificate or storage."""
    training = db.get(TrainingSession, training_id)
    if not training:
        raise HTTPException(404, "Eğitim kaydı bulunamadı.")
    ensure_company_access(db, user, training.company_id)
    return training_presentation_readiness(db, training=training)
