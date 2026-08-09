"""Additive instructor editor and Teaching V3 routes for NACE presentations."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import require_roles
from app.core.config import nace_training_presentation_active
from app.core.database import get_db
from app.models.entities import TrainingSession, User, UserRole
from app.services.training_presentation_editor import (
    PresentationEditError,
    create_edited_draft_version,
)
from app.services.training_presentation_generation import PresentationGenerationError
from app.services.training_presentation_teaching_generation import (
    generate_and_store_teaching_version,
    teaching_generation_payload,
)
from app.services.training_presentation_versions import get_presentation_version, version_payload

router = APIRouter(prefix="/trainings", tags=["NACE Eğitim Sunumu Editörü"])
INSTRUCTOR_EDIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
)


class SlideEditRequest(BaseModel):
    position: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=220)
    mode: Literal["append", "replace"] = "append"
    lesson_points: list[str] = Field(default_factory=list, max_length=8)
    scenario: str | None = Field(default=None, max_length=900)
    key_takeaway: str | None = Field(default=None, max_length=500)
    instructor_note: str | None = Field(default=None, max_length=1400)


class AppendSlideRequest(BaseModel):
    title: str = Field(min_length=3, max_length=220)
    lesson_points: list[str] = Field(default_factory=list, max_length=8)
    scenario: str | None = Field(default=None, max_length=900)
    key_takeaway: str | None = Field(default=None, max_length=500)
    instructor_note: str | None = Field(default=None, max_length=1400)


class PresentationEditCopyRequest(BaseModel):
    slide_updates: list[SlideEditRequest] = Field(default_factory=list, max_length=12)
    append_slides: list[AppendSlideRequest] = Field(default_factory=list, max_length=8)
    change_note: str | None = Field(default=None, max_length=800)
    auto_enrich_teaching_v3: bool = False


def _training_or_404(db: Session, training_id: int) -> TrainingSession:
    training = db.get(TrainingSession, training_id)
    if training is None:
        raise HTTPException(404, "Eğitim kaydı bulunamadı.")
    return training


def _version_or_404(db: Session, *, training_id: int, version_id: int):
    row = get_presentation_version(db, training_id=training_id, version_id=version_id)
    if row is None:
        raise HTTPException(404, "Sunum sürümü bulunamadı.")
    return row


def _ensure_feature(training: TrainingSession) -> None:
    if nace_training_presentation_active(getattr(training, "company_id", None)):
        return
    raise HTTPException(409, {
        "code": "pilot_access_denied",
        "message": "NACE eğitim sunumu bu şirket için kontrollü pilot erişimine açık değildir.",
        "core_training_unaffected": True,
    })


@router.post("/{training_id}/presentation-versions/{version_id}/edit-copy", status_code=201)
def edit_presentation_copy(
    training_id: int,
    version_id: int,
    payload: PresentationEditCopyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*INSTRUCTOR_EDIT_ROLES)),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    _ensure_feature(training)
    source = _version_or_404(db, training_id=training.id, version_id=version_id)
    try:
        row = create_edited_draft_version(
            db,
            source_row=source,
            created_by_id=getattr(user, "id", None),
            slide_updates=[item.model_dump() for item in payload.slide_updates],
            append_slides=[item.model_dump() for item in payload.append_slides],
            change_note=payload.change_note,
            auto_enrich_teaching_v3=payload.auto_enrich_teaching_v3,
        )
        db.commit(); db.refresh(row)
    except PresentationEditError as exc:
        db.rollback()
        raise HTTPException(409, {
            "code": exc.code,
            "message": exc.detail,
            "core_training_unaffected": True,
            "source_version_unchanged": True,
        }) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, {
            "code": "version_conflict",
            "message": "Aynı eğitim için eşzamanlı yeni sunum sürümü oluşturuldu; yeniden deneyin.",
            "core_training_unaffected": True,
        }) from exc
    result = version_payload(row, include_manifest=True)
    result["editor_copy"] = True
    result["source_version_id"] = source.id
    return result


@router.post("/{training_id}/presentation-versions/{version_id}/render-teaching-v3")
def render_teaching_v3(
    training_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*INSTRUCTOR_EDIT_ROLES)),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    _ensure_feature(training)
    row = _version_or_404(db, training_id=training.id, version_id=version_id)
    try:
        generated = generate_and_store_teaching_version(db, row=row)
    except PresentationGenerationError as exc:
        raise HTTPException(
            409 if exc.code in {"pilot_access_denied", "invalid_version_status", "teaching_v3_not_ready", "traceability_not_ready"} else 503,
            {"code": exc.code, "message": exc.detail, "core_training_unaffected": True},
        ) from exc
    return teaching_generation_payload(generated)
