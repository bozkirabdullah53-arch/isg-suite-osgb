"""Optional NACE training presentation API — safe Phase 1–4 boundary."""
from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import TrainingSession, User, UserRole
from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_exact_question_factory import exact_question_readiness
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


def _generation_http_error(exc: PresentationGenerationError) -> HTTPException:
    client_conflicts = {
        "feature_disabled",
        "invalid_version_status",
        "invalid_manifest_json",
        "invalid_manifest_hash",
        "manifest_snapshot_mismatch",
        "unsupported_output_format",
        "output_not_ready",
    }
    status = 409 if exc.code in client_conflicts else 503
    return HTTPException(
        status,
        {
            "code": exc.code,
            "message": exc.detail,
            "core_training_unaffected": True,
        },
    )


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
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    return training_presentation_readiness(db, training=training)


@router.get("/{training_id}/presentation-manifest-preview")
def presentation_manifest_preview(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Build a deterministic preview only; no DB/file/storage write occurs."""
    training = _training_or_404(db, training_id)
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


@router.get("/{training_id}/presentation-versions")
def presentation_versions(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List historical versions even when new generation is switched off."""
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    rows = list_presentation_versions(db, training_id=training.id)
    return {
        "training_id": training.id,
        "count": len(rows),
        "rows": [version_payload(row) for row in rows],
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
    return version_payload(row, include_manifest=True)


@router.post("/{training_id}/presentation-versions", status_code=201)
def create_presentation_version(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Create an immutable draft only; renderer and storage remain untouched."""
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
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
    return version_payload(row, include_manifest=True)


@router.post("/{training_id}/presentation-versions/{version_id}/render")
def render_presentation_version(
    training_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Render both PPTX and PDF, atomically store and hash-verify them."""
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    row = _version_or_404(db, training_id=training.id, version_id=version_id)
    try:
        generated = generate_and_store_version(db, row=row)
    except PresentationGenerationError as exc:
        raise _generation_http_error(exc) from exc
    return generation_status_payload(generated)


@router.get("/{training_id}/presentation-versions/{version_id}/download/{output_format}")
def download_presentation_version(
    training_id: int,
    version_id: int,
    output_format: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download one historical output after checking company access and SHA-256."""
    training = _training_or_404(db, training_id)
    ensure_company_access(db, user, training.company_id)
    row = _version_or_404(db, training_id=training.id, version_id=version_id)
    try:
        download = read_generated_output(
            row=row,
            output_format=output_format,
        )
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
