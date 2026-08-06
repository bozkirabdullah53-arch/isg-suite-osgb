"""Dijital Personel Kartı sıradan belge ve CV API'leri."""
from __future__ import annotations

from datetime import date
from io import BytesIO

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.personnel_profile_config import personnel_profile_card_active
from app.models.entities import User
from app.schemas.personnel_profile_document import (
    PersonnelProfileDocumentArchive,
    PersonnelProfileDocumentMetadata,
)
from app.services.personnel_profile_core import get_profile_or_404
from app.services.personnel_profile_document import (
    MAX_PROFILE_DOCUMENT_BYTES,
    archive_profile_document_version,
    delete_new_upload_after_failed_commit,
    document_payload,
    list_latest_profile_documents,
    list_profile_document_versions,
    load_profile_document_content,
    upload_profile_document_version,
)
from app.services.personnel_profile_file_security import prepare_profile_upload


router = APIRouter(tags=["Dijital Personel Kartı Belgeleri"])


def _require_document_writes_active(company_id: int) -> None:
    if not personnel_profile_card_active(company_id):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=409,
            detail={
                "code": "personnel_profile_disabled",
                "message": (
                    "Dijital Personel Kartı belge işlemleri bu işyeri için kapalıdır. "
                    "Mevcut personel ve belge akışları etkilenmeden devam eder."
                ),
            },
        )


@router.post("/{profile_id}/documents/upload")
async def upload_profile_document(
    profile_id: int,
    file: UploadFile = File(...),
    document_kind: str = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    document_key: str | None = Form(default=None),
    document_number: str | None = Form(default=None),
    issuing_organization: str | None = Form(default=None),
    issue_date: date | None = Form(default=None),
    valid_from: date | None = Form(default=None),
    expiration_date: date | None = Form(default=None),
    no_expiration: bool = Form(default=False),
    access_classification: str = Form(default="internal_only"),
    change_reason: str | None = Form(default=None),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=36,
        max_length=80,
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_profile_or_404(db, profile_id)
    _require_document_writes_active(profile.company_id)
    metadata = PersonnelProfileDocumentMetadata(
        document_kind=document_kind,
        category=category,
        title=title,
        document_key=document_key,
        document_number=document_number,
        issuing_organization=issuing_organization,
        issue_date=issue_date,
        valid_from=valid_from,
        expiration_date=expiration_date,
        no_expiration=no_expiration,
        access_classification=access_classification,
        change_reason=change_reason,
    )
    row = None
    created = False
    new_object_key = None
    try:
        content = await file.read(MAX_PROFILE_DOCUMENT_BYTES + 1)
        safe_content = prepare_profile_upload(
            content,
            filename=file.filename or "upload",
            document_kind=metadata.document_kind,
        )
        row, created = upload_profile_document_version(
            db,
            user=user,
            profile_id=profile_id,
            metadata=metadata,
            idempotency_key=idempotency_key,
            filename=file.filename or "upload",
            content=safe_content,
        )
        if created:
            new_object_key = row.object_key
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        if created:
            delete_new_upload_after_failed_commit(new_object_key)
        raise
    finally:
        await file.close()

    return {
        "created": created,
        "document": document_payload(row),
    }


@router.get("/{profile_id}/documents")
def get_profile_documents(
    profile_id: int,
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {
        "items": list_latest_profile_documents(
            db,
            user=user,
            profile_id=profile_id,
            include_archived=include_archived,
        )
    }


@router.get("/{profile_id}/documents/{document_key}/versions")
def get_profile_document_versions(
    profile_id: int,
    document_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {
        "items": list_profile_document_versions(
            db,
            user=user,
            profile_id=profile_id,
            document_key=document_key,
        )
    }


@router.post("/{profile_id}/documents/{document_key}/archive")
def archive_profile_document(
    profile_id: int,
    document_key: str,
    payload: PersonnelProfileDocumentArchive,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=36,
        max_length=80,
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_profile_or_404(db, profile_id)
    _require_document_writes_active(profile.company_id)
    try:
        row, created = archive_profile_document_version(
            db,
            user=user,
            profile_id=profile_id,
            document_key=document_key,
            reason=payload.reason,
            idempotency_key=idempotency_key,
        )
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise
    return {
        "created": created,
        "document": document_payload(row),
    }


@router.get("/{profile_id}/document-versions/{document_id}/download")
def download_profile_document_version(
    profile_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        row, content, safe_name = load_profile_document_content(
            db,
            user=user,
            profile_id=profile_id,
            document_id=document_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return StreamingResponse(
        BytesIO(content),
        media_type=row.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
