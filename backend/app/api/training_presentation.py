"""Optional NACE training presentation API — safe Phase 1–7 boundary."""
from __future__ import annotations

from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import nace_training_presentation_active
from app.core.database import get_db
from app.models.entities import TrainingSession, User, UserRole
from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_exact_question_factory import exact_question_readiness
from app.services.training_presentation_approval import (
    PresentationApprovalError,
    approval_payload,
    approve_presentation_version,
    archive_presentation_version,
    get_presentation_approval,
)
from app.services.training_presentation_contract import (
    PresentationContractError,
    build_presentation_manifest_preview,
    presentation_contract_payload,
)
from app.services.training_presentation_generation import (
    PresentationGenerationError,
    generate_and_store_version,
    generation_status_payload,
    read_generated_output,
)
from app.services.training_presentation_readiness import training_presentation_readiness
from app.services.training_presentation_versions import (
    PresentationVersionError,
    create_draft_version,
    get_presentation_version,
    list_presentation_versions,
    version_payload,
)

router = APIRouter(prefix="/trainings", tags=["NACE Eğitim Sunumu"])
EDIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
)


class PresentationApprovalRequest(BaseModel):
    approval_method: Literal["application_approval", "qualified_esign"] = "application_approval"
    confirmed_manifest_hash: str = Field(min_length=64, max_length=64)
    approval_note: str | None = Field(default=None, max_length=2000)
    esign_request_id: int | None = Field(default=None, ge=1)


def _training_or_404(db: Session, training_id: int) -> TrainingSession:
    training = db.get(TrainingSession, training_id)
    if not training:
        raise HTTPException(404, "Eğitim kaydı bulunamadı.")
    return training


def _version_or_404(db: Session, *, training_id: int, version_id: int):
    row = get_presentation_version(
        db,
        training_id=training_id,
        version_id=version_id,
    )
    if row is None:
        raise HTTPException(404, "Sunum sürümü bulunamadı.")
    return row


def _ensure_pilot_access(training: TrainingSession) -> None:
    if nace_training_presentation_active(getattr(training, "company_id", None)):
        return
    raise HTTPException(
        409,
        {
            "code": "pilot_access_denied",
            "message": "NACE eğitim sunumu bu şirket için kontrollü pilot erişimine açık değildir.",
            "core_training_unaffected": True,
        },
    )


def _generation_http_error(exc: PresentationGenerationError) -> HTTPException:
    client_conflicts = {
        "feature_disabled",
        "pilot_access_denied",
        "invalid_version_status",
        "invalid_manifest_json",
        "invalid_manifest_hash",
        "manifest_snapshot_mismatch",
        "unsupported_output_format",
        "output_not_ready",
    }
    return HTTPException(
        409 if exc.code in client_conflicts else 503,
        {
            "code": exc.code,
            "message": exc.detail,
            "core_training_unaffected": True,
        },
    )


def _approval_http_error(exc: PresentationApprovalError) -> HTTPException:
    unavailable = {
        "esign_request_missing",
        "esign_not_verified",
        "esign_signed_hash_missing",
        "esign_revocation_invalid",
    }
    return HTTPException(
        503 if exc.code in unavailable else 409,
        {
            "code": exc.code,
            "message": exc.detail,
            "core_training_unaffected": True,
        },
    )


def _version_with_approval(db: Session, row, *, include_manifest: bool = False) -> dict:
    payload = version_payload(row, include_manifest=include_manifest)
    raw_status = getattr(row, "status", "")
    status = str(getattr(raw_status, "value", raw_status) or "").lower()
    if status in {"approved", "archived"}:
        approval = get_presentation_approval(db, presentation_version_id=row.id)
        if approval is not None:
            payload["approval"] = approval_payload(approval)
    return payload


@router.get("/presentation-contract")
def presentation_contract(user: User = Depends(get_current_user)):
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
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    return training_presentation_readiness(db, training=training)


@router.get("/{training_id}/presentation-manifest-preview")
def presentation_manifest_preview(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    _ensure_pilot_access(training)
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


@router.get("/{training_id}/presentation-versions")
def presentation_versions(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    rows = list_presentation_versions(db, training_id=training.id)
    return {
        "training_id": training.id,
        "count": len(rows),
        "rows": [_version_with_approval(db, row) for row in rows],
        "read_only_history": True,
    }


@router.get("/{training_id}/presentation-versions/{version_id}")
def presentation_version_detail(
    training_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    row = _version_or_404(db, training_id=training.id, version_id=version_id)
    return _version_with_approval(db, row, include_manifest=True)


@router.post("/{training_id}/presentation-versions", status_code=201)
def create_presentation_version(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    _ensure_pilot_access(training)
    try:
        row = create_draft_version(
            db,
            training=training,
            created_by_id=getattr(user, "id", None),
        )
        db.commit()
        db.refresh(row)
    except PresentationVersionError as exc:
        db.rollback()
        raise HTTPException(
            409,
            {
                "code": exc.code,
                "message": exc.detail,
                "core_training_unaffected": True,
                "renderer_available": True,
                "storage_write": False,
            },
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            {
                "code": "version_conflict",
                "message": "Aynı eğitim için sunum sürümü eşzamanlı oluşturuldu; tekrar deneyin.",
                "core_training_unaffected": True,
            },
        ) from exc
    return _version_with_approval(db, row, include_manifest=True)


@router.post("/{training_id}/presentation-versions/{version_id}/render")
def render_presentation_version(
    training_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    _ensure_pilot_access(training)
    row = _version_or_404(db, training_id=training.id, version_id=version_id)
    try:
        generated = generate_and_store_version(db, row=row)
    except PresentationGenerationError as exc:
        raise _generation_http_error(exc) from exc
    return generation_status_payload(generated)


@router.get("/{training_id}/presentation-versions/{version_id}/approval")
def presentation_version_approval(
    training_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    row = _version_or_404(db, training_id=training.id, version_id=version_id)
    approval = get_presentation_approval(db, presentation_version_id=row.id)
    return {
        "training_id": training.id,
        "version_id": row.id,
        "approved": approval is not None,
        "approval": approval_payload(approval) if approval else None,
        "read_only": True,
    }


@router.post("/{training_id}/presentation-versions/{version_id}/approve", status_code=201)
def approve_presentation(
    training_id: int,
    version_id: int,
    payload: PresentationApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    _ensure_pilot_access(training)
    row = _version_or_404(db, training_id=training.id, version_id=version_id)
    try:
        approval = approve_presentation_version(
            db,
            row=row,
            user=user,
            method=payload.approval_method,
            confirmed_manifest_hash=payload.confirmed_manifest_hash,
            note=payload.approval_note,
            esign_request_id=payload.esign_request_id,
        )
        db.commit()
        db.refresh(approval)
        db.refresh(row)
    except PresentationApprovalError as exc:
        db.rollback()
        raise _approval_http_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            {
                "code": "approval_conflict",
                "message": "Bu sürüm için onay kaydı zaten oluşturulmuş olabilir.",
                "core_training_unaffected": True,
            },
        ) from exc
    return {
        "version": _version_with_approval(db, row),
        "approval": approval_payload(approval),
    }


@router.post("/{training_id}/presentation-versions/{version_id}/archive")
def archive_presentation(
    training_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    _ensure_pilot_access(training)
    row = _version_or_404(db, training_id=training.id, version_id=version_id)
    try:
        archived = archive_presentation_version(db, row=row, user=user)
        db.commit()
        db.refresh(archived)
    except PresentationApprovalError as exc:
        db.rollback()
        raise _approval_http_error(exc) from exc
    return _version_with_approval(db, archived)


@router.get("/{training_id}/presentation-versions/{version_id}/download/{output_format}")
def download_presentation_version(
    training_id: int,
    version_id: int,
    output_format: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    row = _version_or_404(db, training_id=training.id, version_id=version_id)
    try:
        download = read_generated_output(row=row, output_format=output_format)
    except PresentationGenerationError as exc:
        raise _generation_http_error(exc) from exc
    headers = {
        "Content-Disposition": f'attachment; filename="{download.filename}"',
        "X-Content-SHA256": download.file_hash,
        "Cache-Control": "private, no-store",
    }
    return StreamingResponse(
        BytesIO(download.content),
        media_type=download.content_type,
        headers=headers,
    )
