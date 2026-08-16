"""OSGB-only Digital Professional Card API overlay.

All routes live under /osgb-personnel-profiles so legacy workplace Employee
profile routes remain untouched. Workplace employees are intentionally absent.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, reject_company_bound_admin_from_osgb_internal
from app.api.personnel_profile_documents import _TrackedObjectStore, _private_profile_object_store
from app.core.database import get_db
from app.models.entities import User
from app.models.personnel_profile import (
    PersonnelProfile,
    PersonnelProfileCompetency,
    PersonnelProfileContact,
    PersonnelProfileExperience,
)
from app.schemas.personnel_profile import (
    PersonnelCompetencyVersionCreate,
    PersonnelContactVersionCreate,
    PersonnelExperienceVersionCreate,
)
from app.schemas.personnel_profile_document import (
    PersonnelProfileDocumentArchive,
    PersonnelProfileDocumentMetadata,
)
from app.schemas.personnel_profile_management import PersonnelProfileEntryArchive, validate_profile_entry_key
from app.services.audit import add_audit_log
from app.services.personnel_profile_core import (
    append_competency_version,
    append_contact_version,
    append_experience_version,
    profile_snapshot,
)
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
from app.services.personnel_profile_osgb_scope import (
    archive_osgb_profile,
    initialize_osgb_professional_profile,
    list_osgb_professionals,
    professional_summary,
    require_osgb_access,
    require_osgb_feature,
    require_osgb_profile_read,
    require_osgb_profile_write,
)

_OSGB_INTERNAL_DEPENDENCIES = [Depends(reject_company_bound_admin_from_osgb_internal)]
osgb_router = APIRouter(
    prefix="/osgb-personnel-profiles",
    tags=["OSGB Dijital Profesyonel Kartı"],
    dependencies=_OSGB_INTERNAL_DEPENDENCIES,
)
profile_router = APIRouter(
    prefix="/osgb-personnel-profiles",
    tags=["OSGB Dijital Profesyonel Kartı"],
    dependencies=_OSGB_INTERNAL_DEPENDENCIES,
)


def _commit_retry(db: Session, operation):
    try:
        result = operation()
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        try:
            result = operation()
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
    except Exception:
        db.rollback()
        raise


@osgb_router.get("/readiness")
def osgb_profile_readiness(
    osgb_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_osgb_access(db, user, osgb_id)
    rollout = require_osgb_feature(osgb_id)
    return {
        "readiness_version": "osgb-professional-card-v1",
        "osgb_id": int(osgb_id),
        "enabled": True,
        "visible": True,
        "scope": "osgb_professionals_only",
        "employee_records_included": False,
        "assignment_required_for_visibility": False,
        "rollout": rollout,
    }


@osgb_router.get("/professionals")
def osgb_professional_cards(
    osgb_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = list_osgb_professionals(db, user=user, osgb_id=osgb_id)
    return {
        "items": [
            {
                "id": row.id,
                "osgb_id": row.osgb_id,
                "full_name": row.full_name,
                "email": row.email,
                "phone": row.phone,
                "professional_type": getattr(row.professional_type, "value", row.professional_type),
                "certificate_class": row.certificate_class,
                "certificate_number": row.certificate_number,
                "certificate_date": row.certificate_date.isoformat() if row.certificate_date else None,
                "is_active": bool(row.is_active),
            }
            for row in rows
        ]
    }


@osgb_router.get("/professional/{professional_id}/summary")
def get_osgb_professional_summary(
    professional_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return professional_summary(db, user=user, professional_id=professional_id)


@osgb_router.post("/professionals/{professional_id}")
def initialize_osgb_profile(
    professional_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile, created = _commit_retry(
        db,
        lambda: initialize_osgb_professional_profile(
            db, user=user, professional_id=professional_id
        ),
    )
    db.refresh(profile)
    snapshot = profile_snapshot(db, profile)
    return {"created": created, "profile": snapshot["profile"], "privacy": snapshot["privacy"]}


@profile_router.get("/{profile_id}")
def get_osgb_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = db.get(PersonnelProfile, profile_id)
    if not profile or profile.subject_type != "professional" or profile.company_id is not None:
        raise HTTPException(404, "OSGB profesyonel kartı bulunamadı.")
    require_osgb_profile_read(db, user, profile)
    return profile_snapshot(db, profile)


@profile_router.post("/{profile_id}/contacts")
def add_osgb_contact(
    profile_id: int,
    payload: PersonnelContactVersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_osgb_profile_write(db, user, profile_id)
    row, created = _commit_retry(
        db,
        lambda: append_contact_version(db, user=user, profile_id=profile_id, payload=payload),
    )
    db.refresh(row)
    return {"created": created, "id": row.id, "entry_key": row.entry_key, "version": row.version, "verification_status": row.verification_status, "lifecycle_status": row.lifecycle_status}


@profile_router.post("/{profile_id}/competencies")
def add_osgb_competency(
    profile_id: int,
    payload: PersonnelCompetencyVersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_osgb_profile_write(db, user, profile_id)
    row, created = _commit_retry(
        db,
        lambda: append_competency_version(db, user=user, profile_id=profile_id, payload=payload),
    )
    db.refresh(row)
    return {"created": created, "id": row.id, "entry_key": row.entry_key, "version": row.version, "verification_status": row.verification_status, "lifecycle_status": row.lifecycle_status}


@profile_router.post("/{profile_id}/experiences")
def add_osgb_experience(
    profile_id: int,
    payload: PersonnelExperienceVersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_osgb_profile_write(db, user, profile_id)
    row, created = _commit_retry(
        db,
        lambda: append_experience_version(db, user=user, profile_id=profile_id, payload=payload),
    )
    db.refresh(row)
    return {"created": created, "id": row.id, "entry_key": row.entry_key, "version": row.version, "lifecycle_status": row.lifecycle_status}


_ENTRY_MODELS = {
    "contacts": PersonnelProfileContact,
    "competencies": PersonnelProfileCompetency,
    "experiences": PersonnelProfileExperience,
}
_COPY_FIELDS = {
    "contacts": ("contact_type", "label", "contact_value", "is_primary", "visibility", "verification_status", "verified_by_id", "verified_at"),
    "competencies": ("category", "name", "start_date", "end_date", "certificate_number", "issuing_organization", "description", "verification_status", "approved_by_id", "approved_at"),
    "experiences": ("organization_name", "position", "start_date", "end_date", "employment_type", "sector", "nace_activity", "project_name", "professional_summary", "responsibilities", "visibility", "approved_by_id", "approved_at"),
}


@profile_router.post("/{profile_id}/entries/{entry_type}/{entry_key}/archive")
def archive_osgb_entry(
    profile_id: int,
    entry_type: str,
    entry_key: str,
    payload: PersonnelProfileEntryArchive,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = require_osgb_profile_write(db, user, profile_id)
    model = _ENTRY_MODELS.get(entry_type)
    if model is None:
        raise HTTPException(404, "Profil kayıt türü bulunamadı.")
    try:
        normalized_key = validate_profile_entry_key(entry_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    latest = db.scalar(
        select(model)
        .where(model.profile_id == profile.id, model.entry_key == normalized_key)
        .order_by(model.version.desc())
        .limit(1)
    )
    if not latest:
        raise HTTPException(404, "Arşivlenecek profil kaydı bulunamadı.")
    if latest.lifecycle_status == "archived":
        return {"created": False, "id": latest.id, "entry_key": latest.entry_key, "version": latest.version, "lifecycle_status": latest.lifecycle_status}
    copied = {field: getattr(latest, field) for field in _COPY_FIELDS[entry_type]}
    row = model(
        profile_id=profile.id,
        company_id=None,
        entry_key=latest.entry_key,
        version=int(latest.version) + 1,
        supersedes_id=latest.id,
        lifecycle_status="archived",
        change_reason=payload.reason,
        created_by_id=user.id,
        **copied,
    )
    try:
        db.add(row)
        db.flush()
        add_audit_log(
            db,
            user=user,
            action=f"osgb_professional_profile_{entry_type}_archived",
            entity_type=f"personnel_profile_{entry_type}",
            entity_id=str(row.id),
            module="personnel_profile",
            description=(
                "OSGB profesyonel kartı girdisi fiziksel silinmeden arşiv sürümüyle kapatıldı; "
                f"profile_id={profile.id}, entry_key={latest.entry_key}, version={row.version}."
            ),
        )
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise
    return {"created": True, "id": row.id, "entry_key": row.entry_key, "version": row.version, "lifecycle_status": row.lifecycle_status}


@profile_router.post("/{profile_id}/archive")
def archive_osgb_card(
    profile_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = require_osgb_profile_write(db, user, profile_id)
    try:
        archive_osgb_profile(db, user=user, profile=profile)
        db.commit()
        db.refresh(profile)
    except Exception:
        db.rollback()
        raise
    return {"id": profile.id, "status": profile.status, "archived_at": profile.archived_at.isoformat() if profile.archived_at else None}


@profile_router.get("/{profile_id}/documents")
def get_osgb_documents(
    profile_id: int,
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_osgb_profile_write(db, user, profile_id)
    return {"items": list_latest_profile_documents(db, user=user, profile_id=profile_id, include_archived=include_archived)}


@profile_router.get("/{profile_id}/documents/{document_key}/versions")
def get_osgb_document_versions(
    profile_id: int,
    document_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_osgb_profile_write(db, user, profile_id)
    return {"items": list_profile_document_versions(db, user=user, profile_id=profile_id, document_key=document_key)}


@profile_router.post("/{profile_id}/documents/upload")
async def upload_osgb_document(
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
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=36, max_length=80),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_osgb_profile_write(db, user, profile_id)
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
    normalized = normalize_idempotency_key(idempotency_key)
    tracked_store = _TrackedObjectStore(_private_profile_object_store())
    try:
        content = await file.read(MAX_PROFILE_DOCUMENT_BYTES + 1)
        safe_content = prepare_profile_upload(content, filename=file.filename or "upload", document_kind=metadata.document_kind)
        row, created = upload_profile_document_version(
            db,
            user=user,
            profile_id=profile_id,
            metadata=metadata,
            idempotency_key=normalized,
            filename=file.filename or "upload",
            content=safe_content,
            store=tracked_store,
        )
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        tracked_store.cleanup_created()
        raise
    finally:
        await file.close()
    return {"created": created, "document": document_payload(row)}


@profile_router.post("/{profile_id}/documents/{document_key}/archive")
def archive_osgb_document(
    profile_id: int,
    document_key: str,
    payload: PersonnelProfileDocumentArchive,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=36, max_length=80),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_osgb_profile_write(db, user, profile_id)
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
    return {"created": created, "document": document_payload(row)}


@profile_router.get("/{profile_id}/document-versions/{document_id}/download")
def download_osgb_document(
    profile_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_osgb_profile_write(db, user, profile_id)
    try:
        row, content, safe_name = load_profile_document_content(
            db,
            user=user,
            profile_id=profile_id,
            document_id=document_id,
            store=_private_profile_object_store(),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return StreamingResponse(
        BytesIO(content),
        media_type=row.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"', "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
