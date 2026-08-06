"""Private object-store personnel profile document versioning.

Only ordinary professional profile files are accepted here. Restricted health,
criminal-record, biometric, salary and disciplinary documents are intentionally
outside this service.
"""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.models.entities import User
from app.models.personnel_profile_document import PersonnelProfileDocument
from app.schemas.personnel_profile_document import PersonnelProfileDocumentMetadata
from app.services.audit import add_audit_log
from app.services.object_store import ObjectStore, get_object_store
from app.services.personnel_profile_core import (
    get_profile_or_404,
    require_profile_write_role,
)
from app.services.upload_security import assert_safe_upload


MAX_PROFILE_DOCUMENT_BYTES = 15 * 1024 * 1024
_KIND_LIMITS = {
    "profile_photo": 5 * 1024 * 1024,
    "cv": 10 * 1024 * 1024,
    "qualification": MAX_PROFILE_DOCUMENT_BYTES,
    "certificate": MAX_PROFILE_DOCUMENT_BYTES,
}
_KIND_EXTENSIONS = {
    "profile_photo": {".png", ".jpg", ".jpeg", ".webp"},
    "cv": {".pdf", ".docx"},
    "qualification": {".pdf", ".png", ".jpg", ".jpeg", ".webp"},
    "certificate": {".pdf", ".png", ".jpg", ".jpeg", ".webp"},
}
_MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def normalize_idempotency_key(value: str) -> str:
    try:
        return str(UUID(str(value or "").strip()))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            422,
            "Idempotency-Key geçerli bir UUID olmalıdır.",
        ) from exc


def _normalize_extension(filename: str) -> str:
    extension = Path(filename or "").suffix.lower()
    if not extension:
        raise HTTPException(400, "Dosya uzantısı gerekli.")
    return extension


def _require_document_access(db: Session, user: User, profile_id: int):
    require_profile_write_role(user)
    profile = get_profile_or_404(db, profile_id)
    ensure_company_access(db, user, profile.company_id)
    return profile


def _validate_upload(
    *,
    content: bytes,
    filename: str,
    document_kind: str,
) -> tuple[str, str, str]:
    extension = _normalize_extension(filename)
    allowed_extensions = _KIND_EXTENSIONS[document_kind]
    if extension not in allowed_extensions:
        raise HTTPException(
            400,
            f"{document_kind} için desteklenmeyen dosya türü.",
        )
    limit = _KIND_LIMITS[document_kind]
    if not content:
        raise HTTPException(400, "Boş dosya yüklenemez.")
    if len(content) > limit:
        raise HTTPException(
            413,
            f"Dosya bu kategori için {limit // (1024 * 1024)} MB sınırını aşıyor.",
        )
    assert_safe_upload(content, extension, filename)
    return extension, _MIME_BY_EXTENSION[extension], sha256(content).hexdigest()


def _latest_document(
    db: Session,
    *,
    profile_id: int,
    document_key: str,
) -> PersonnelProfileDocument | None:
    return db.scalar(
        select(PersonnelProfileDocument)
        .where(
            PersonnelProfileDocument.profile_id == profile_id,
            PersonnelProfileDocument.document_key == document_key,
        )
        .order_by(PersonnelProfileDocument.version.desc())
        .limit(1)
    )


def _by_idempotency(
    db: Session,
    *,
    profile_id: int,
    idempotency_key: str,
) -> PersonnelProfileDocument | None:
    return db.scalar(
        select(PersonnelProfileDocument)
        .where(
            PersonnelProfileDocument.profile_id == profile_id,
            PersonnelProfileDocument.idempotency_key == idempotency_key,
        )
        .limit(1)
    )


def _same_upload(
    row: PersonnelProfileDocument,
    *,
    checksum: str,
    metadata: PersonnelProfileDocumentMetadata,
) -> bool:
    return (
        row.checksum_sha256 == checksum
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


def upload_profile_document_version(
    db: Session,
    *,
    user: User,
    profile_id: int,
    metadata: PersonnelProfileDocumentMetadata,
    idempotency_key: str,
    filename: str,
    content: bytes,
    store: ObjectStore | None = None,
) -> tuple[PersonnelProfileDocument, bool]:
    """Store a new immutable file version or return an idempotent prior result."""

    profile = _require_document_access(db, user, profile_id)
    if profile.status != "active":
        raise HTTPException(409, "Arşivlenmiş profile belge eklenemez.")

    normalized_idempotency = normalize_idempotency_key(idempotency_key)
    extension, mime_type, checksum = _validate_upload(
        content=content,
        filename=filename,
        document_kind=metadata.document_kind,
    )

    prior_request = _by_idempotency(
        db,
        profile_id=profile.id,
        idempotency_key=normalized_idempotency,
    )
    if prior_request:
        if _same_upload(prior_request, checksum=checksum, metadata=metadata):
            return prior_request, False
        raise HTTPException(
            409,
            "Aynı Idempotency-Key farklı bir belge isteğinde kullanılamaz.",
        )

    document_key = (
        str(metadata.document_key)
        if metadata.document_key is not None
        else str(uuid4())
    )
    previous = _latest_document(
        db,
        profile_id=profile.id,
        document_key=document_key,
    )
    if previous:
        if previous.lifecycle_status == "archived":
            raise HTTPException(
                409,
                "Arşivlenmiş belge yeniden sürümlenemez; yeni belge kaydı oluşturun.",
            )
        if (
            previous.document_kind != metadata.document_kind
            or previous.category != metadata.category
        ):
            raise HTTPException(
                409,
                "Yeni sürüm mevcut belgenin türü ve kategorisiyle aynı olmalıdır.",
            )

    version = int(previous.version) + 1 if previous else 1
    object_key = (
        f"osgb/companies/{profile.company_id}/personnel/{profile.id}/"
        f"{metadata.document_kind}/{document_key}/versions/{version}/"
        f"{uuid4().hex}{extension}"
    )
    active_store = store or get_object_store()
    active_store.put_bytes(object_key, content)

    row = PersonnelProfileDocument(
        profile_id=profile.id,
        company_id=profile.company_id,
        document_key=document_key,
        version=version,
        supersedes_id=previous.id if previous else None,
        idempotency_key=normalized_idempotency,
        document_kind=metadata.document_kind,
        category=metadata.category,
        title=metadata.title,
        document_number=metadata.document_number,
        issuing_organization=metadata.issuing_organization,
        issue_date=metadata.issue_date,
        valid_from=metadata.valid_from,
        expiration_date=metadata.expiration_date,
        no_expiration=metadata.no_expiration,
        object_key=object_key,
        mime_type=mime_type,
        file_extension=extension,
        file_size=len(content),
        checksum_sha256=checksum,
        access_classification=metadata.access_classification,
        processing_purpose="professional_profile_management",
        retention_policy="personnel_profile_ordinary_v1",
        verification_status="unverified",
        lifecycle_status="active",
        change_reason=metadata.change_reason,
        created_by_id=user.id,
    )
    db.add(row)
    try:
        db.flush()
    except Exception:
        try:
            active_store.delete(object_key)
        except Exception:
            pass
        raise

    add_audit_log(
        db,
        user=user,
        action="personnel_profile_document_uploaded",
        entity_type="personnel_profile_document",
        entity_id=str(row.id),
        module="personnel_profile",
        description=(
            "Sıradan profil belgesi private object-store katmanına sürümlü yüklendi; "
            f"profile_id={profile.id}, category={row.category}, "
            f"document_key={row.document_key}, version={row.version}, "
            f"checksum_prefix={row.checksum_sha256[:12]}."
        ),
    )
    return row, True


def archive_profile_document_version(
    db: Session,
    *,
    user: User,
    profile_id: int,
    document_key: str,
    reason: str,
    idempotency_key: str,
) -> tuple[PersonnelProfileDocument, bool]:
    """Append an archived version without deleting any stored object."""

    profile = _require_document_access(db, user, profile_id)
    if profile.status != "active":
        raise HTTPException(409, "Arşivlenmiş profil üzerinde belge işlemi yapılamaz.")

    try:
        normalized_document_key = str(UUID(str(document_key)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "Belge anahtarı geçersiz.") from exc
    normalized_idempotency = normalize_idempotency_key(idempotency_key)

    prior_request = _by_idempotency(
        db,
        profile_id=profile.id,
        idempotency_key=normalized_idempotency,
    )
    if prior_request:
        if (
            prior_request.document_key == normalized_document_key
            and prior_request.lifecycle_status == "archived"
        ):
            return prior_request, False
        raise HTTPException(
            409,
            "Aynı Idempotency-Key farklı bir belge işleminde kullanılamaz.",
        )

    latest = _latest_document(
        db,
        profile_id=profile.id,
        document_key=normalized_document_key,
    )
    if latest is None:
        raise HTTPException(404, "Arşivlenecek belge bulunamadı.")
    if latest.lifecycle_status == "archived":
        return latest, False

    row = PersonnelProfileDocument(
        profile_id=latest.profile_id,
        company_id=latest.company_id,
        document_key=latest.document_key,
        version=int(latest.version) + 1,
        supersedes_id=latest.id,
        idempotency_key=normalized_idempotency,
        document_kind=latest.document_kind,
        category=latest.category,
        title=latest.title,
        document_number=latest.document_number,
        issuing_organization=latest.issuing_organization,
        issue_date=latest.issue_date,
        valid_from=latest.valid_from,
        expiration_date=latest.expiration_date,
        no_expiration=latest.no_expiration,
        object_key=latest.object_key,
        mime_type=latest.mime_type,
        file_extension=latest.file_extension,
        file_size=latest.file_size,
        checksum_sha256=latest.checksum_sha256,
        access_classification=latest.access_classification,
        processing_purpose=latest.processing_purpose,
        retention_policy=latest.retention_policy,
        verification_status=latest.verification_status,
        lifecycle_status="archived",
        change_reason=reason,
        created_by_id=user.id,
        verified_by_id=latest.verified_by_id,
        verified_at=latest.verified_at,
    )
    db.add(row)
    db.flush()
    add_audit_log(
        db,
        user=user,
        action="personnel_profile_document_archived",
        entity_type="personnel_profile_document",
        entity_id=str(row.id),
        module="personnel_profile",
        description=(
            "Profil belgesi fiziksel silinmeden arşiv sürümüyle sonlandırıldı; "
            f"profile_id={profile.id}, document_key={row.document_key}, "
            f"version={row.version}."
        ),
    )
    return row, True


def _validity_status(row: PersonnelProfileDocument, *, today: date | None = None) -> str:
    current = today or date.today()
    if row.lifecycle_status == "archived":
        return "archived"
    if row.no_expiration:
        return "no_expiration"
    if row.expiration_date is None:
        return "incomplete"
    if row.expiration_date < current:
        return "expired"
    if row.expiration_date <= current + timedelta(days=30):
        return "expiring_soon"
    return "valid"


def document_payload(row: PersonnelProfileDocument) -> dict[str, Any]:
    """Return metadata only; never expose object keys or permanent URLs."""

    return {
        "id": row.id,
        "profile_id": row.profile_id,
        "document_key": row.document_key,
        "version": row.version,
        "supersedes_id": row.supersedes_id,
        "document_kind": row.document_kind,
        "category": row.category,
        "title": row.title,
        "document_number": row.document_number,
        "issuing_organization": row.issuing_organization,
        "issue_date": row.issue_date.isoformat() if row.issue_date else None,
        "valid_from": row.valid_from.isoformat() if row.valid_from else None,
        "expiration_date": (
            row.expiration_date.isoformat() if row.expiration_date else None
        ),
        "no_expiration": bool(row.no_expiration),
        "mime_type": row.mime_type,
        "file_extension": row.file_extension,
        "file_size": row.file_size,
        "checksum_sha256": row.checksum_sha256,
        "access_classification": row.access_classification,
        "verification_status": row.verification_status,
        "lifecycle_status": row.lifecycle_status,
        "validity_status": _validity_status(row),
        "processing_purpose": row.processing_purpose,
        "retention_policy": row.retention_policy,
        "change_reason": row.change_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_latest_profile_documents(
    db: Session,
    *,
    user: User,
    profile_id: int,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    profile = _require_document_access(db, user, profile_id)
    latest = (
        select(
            PersonnelProfileDocument.document_key.label("document_key"),
            func.max(PersonnelProfileDocument.version).label("version"),
        )
        .where(PersonnelProfileDocument.profile_id == profile.id)
        .group_by(PersonnelProfileDocument.document_key)
        .subquery()
    )
    rows = list(
        db.scalars(
            select(PersonnelProfileDocument)
            .join(
                latest,
                and_(
                    PersonnelProfileDocument.document_key == latest.c.document_key,
                    PersonnelProfileDocument.version == latest.c.version,
                ),
            )
            .where(PersonnelProfileDocument.profile_id == profile.id)
            .order_by(
                PersonnelProfileDocument.document_kind,
                PersonnelProfileDocument.category,
                PersonnelProfileDocument.created_at.desc(),
            )
        ).all()
    )
    if not include_archived:
        rows = [row for row in rows if row.lifecycle_status != "archived"]
    return [document_payload(row) for row in rows]


def list_profile_document_versions(
    db: Session,
    *,
    user: User,
    profile_id: int,
    document_key: str,
) -> list[dict[str, Any]]:
    profile = _require_document_access(db, user, profile_id)
    try:
        normalized = str(UUID(str(document_key)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "Belge anahtarı geçersiz.") from exc
    rows = list(
        db.scalars(
            select(PersonnelProfileDocument)
            .where(
                PersonnelProfileDocument.profile_id == profile.id,
                PersonnelProfileDocument.document_key == normalized,
            )
            .order_by(PersonnelProfileDocument.version.desc())
        ).all()
    )
    if not rows:
        raise HTTPException(404, "Belge bulunamadı.")
    return [document_payload(row) for row in rows]


def load_profile_document_content(
    db: Session,
    *,
    user: User,
    profile_id: int,
    document_id: int,
    store: ObjectStore | None = None,
) -> tuple[PersonnelProfileDocument, bytes, str]:
    profile = _require_document_access(db, user, profile_id)
    row = db.get(PersonnelProfileDocument, document_id)
    if not row or int(row.profile_id) != int(profile.id):
        raise HTTPException(404, "Belge sürümü bulunamadı.")

    content = (store or get_object_store()).get_bytes(row.object_key)
    if len(content) != int(row.file_size):
        raise HTTPException(409, "Belge boyut doğrulaması başarısız.")
    checksum = sha256(content).hexdigest()
    if checksum != row.checksum_sha256:
        raise HTTPException(409, "Belge bütünlük doğrulaması başarısız.")

    add_audit_log(
        db,
        user=user,
        action="personnel_profile_document_downloaded",
        entity_type="personnel_profile_document",
        entity_id=str(row.id),
        module="personnel_profile",
        description=(
            "Yetkili kullanıcı doğrulanmış profil belge sürümünü indirdi; "
            f"profile_id={profile.id}, document_key={row.document_key}, "
            f"version={row.version}."
        ),
    )
    safe_name = f"personnel-document-{row.document_key}-v{row.version}{row.file_extension}"
    return row, content, safe_name


def delete_new_upload_after_failed_commit(
    object_key: str | None,
    *,
    store: ObjectStore | None = None,
) -> None:
    if not object_key:
        return
    try:
        (store or get_object_store()).delete(object_key)
    except Exception:
        return
