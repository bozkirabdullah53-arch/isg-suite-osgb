"""Dijital Personel Kartı sıradan belge ve CV API'leri."""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from io import BytesIO

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.personnel_profile_config import personnel_profile_card_active
from app.models.entities import User
from app.models.personnel_profile_document import PersonnelProfileDocument
from app.schemas.personnel_profile_document import (
    PersonnelProfileDocumentArchive,
    PersonnelProfileDocumentMetadata,
)
from app.services.object_store import ObjectStore, get_object_store
from app.services.personnel_profile_core import get_profile_or_404
from app.services.personnel_profile_document import (
    MAX_PROFILE_DOCUMENT_BYTES,
    archive_profile_document_version,
    document_payload,
    list_latest_profile_documents,
    list_profile_document_versions,
    load_profile_document_content,
    normalize_idempotency_key,
    upload_profile_document_version,
)
from app.services.personnel_profile_file_security import prepare_profile_upload


router = APIRouter(tags=["Dijital Personel Kartı Belgeleri"])


class _TrackedObjectStore:
    """Tracks only the object created by the current upload transaction."""

    def __init__(self, delegate: ObjectStore) -> None:
        self.delegate = delegate
        self.created_key: str | None = None

    def put_bytes(self, key: str, content: bytes) -> str:
        stored = self.delegate.put_bytes(key, content)
        self.created_key = stored
        return stored

    def get_bytes(self, key: str) -> bytes:
        return self.delegate.get_bytes(key)

    def exists(self, key: str) -> bool:
        return self.delegate.exists(key)

    def delete(self, key: str) -> None:
        self.delegate.delete(key)
        if self.created_key == key:
            self.created_key = None

    def resolve_local_path(self, key: str):
        return self.delegate.resolve_local_path(key)

    def cleanup_created(self) -> None:
        if not self.created_key:
            return
        key = self.created_key
        self.created_key = None
        try:
            self.delegate.delete(key)
        except Exception:
            # Do not mask the original DB/audit/commit failure.
            return


def _require_document_writes_active(company_id: int) -> None:
    if not personnel_profile_card_active(company_id):
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


def _same_retry_request(
    row: PersonnelProfileDocument,
    *,
    metadata: PersonnelProfileDocumentMetadata,
    safe_content: bytes,
) -> bool:
    return (
        row.checksum_sha256 == sha256(safe_content).hexdigest()
        and row.document_kind == metadata.document_kind
        and row.category == metadata.category
        and row.title == metadata.title
        and row.document_number == metadata.document_number
        and row.issuing_organization == metadata.issuing_organization
        and row.issue_date == metadata.issue_date
        and row.valid_from == metadata.valid_from
        and row.expiration_date == metadata.expiration_date
        and bool(row.no_expiration) == bool(metadata.no_expiration)
        and row.access_classification == metadata.access_classification
        and (
            metadata.document_key is None
            or row.document_key == str(metadata.document_key)
        )
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
    normalized_idempotency = normalize_idempotency_key(idempotency_key)
    tracked_store = _TrackedObjectStore(get_object_store())
    safe_content = b""
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
            idempotency_key=normalized_idempotency,
            filename=file.filename or "upload",
            content=safe_content,
            store=tracked_store,
        )
        db.commit()
        db.refresh(row)
    except IntegrityError as exc:
        db.rollback()
        tracked_store.cleanup_created()
        existing = db.scalar(
            select(PersonnelProfileDocument)
            .where(
                PersonnelProfileDocument.profile_id == profile_id,
                PersonnelProfileDocument.idempotency_key == normalized_idempotency,
            )
            .limit(1)
        )
        if existing and _same_retry_request(
            existing,
            metadata=metadata,
            safe_content=safe_content,
        ):
            row = existing
            created = False
        else:
            raise HTTPException(
                409,
                "Belge aynı anda güncellendi veya Idempotency-Key farklı bir istekte kullanıldı.",
            ) from exc
    except Exception:
        db.rollback()
        tracked_store.cleanup_created()
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
