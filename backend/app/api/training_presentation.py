"""Optional NACE training presentation API — read-only Phase 1/2 boundary."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import TrainingSession, User
from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_exact_question_factory import exact_question_readiness
from app.services.training_presentation_contract import (
    PresentationContractError,
    build_presentation_manifest_preview,
    presentation_contract_payload,
)
from app.services.training_presentation_readiness import training_presentation_readiness

router = APIRouter(prefix="/trainings", tags=["NACE Eğitim Sunumu"])


@router.get("/presentation-contract")
def presentation_contract(user: User = Depends(get_current_user)):
    """Return the source-controlled content contract; never render or persist."""
    del user
    try:
        return presentation_contract_payload()
    except PresentationContractError as exc:
        raise HTTPException(503, str(exc)) from exc


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


@router.get("/{training_id}/presentation-manifest-preview")
def presentation_manifest_preview(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Build a deterministic preview only; no DB/file/storage write occurs."""
    training = db.get(TrainingSession, training_id)
    if not training:
        raise HTTPException(404, "Eğitim kaydı bulunamadı.")
    ensure_company_access(db, user, training.company_id)
    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(
            TrainingNaceSnapshot.training_id == training.id
        )
    )
    try:
        return build_presentation_manifest_preview(
            training=training,
            snapshot=snapshot,
            exam_readiness=exact_question_readiness(db, training),
        )
    except PresentationContractError as exc:
        raise HTTPException(
            409,
            {
                "message": str(exc),
                "core_training_unaffected": True,
                "storage_write": False,
            },
        ) from exc
