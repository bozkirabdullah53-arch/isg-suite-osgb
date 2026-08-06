"""Dijital Personel Kartı yönetim API uzantıları."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.personnel_profile_documents import router as documents_router
from app.core.database import get_db
from app.core.personnel_profile_config import personnel_profile_card_active
from app.models.entities import User
from app.schemas.personnel_profile_management import (
    PersonnelProfileEntryArchive,
    validate_profile_entry_key,
)
from app.services.personnel_profile_core import get_profile_or_404
from app.services.personnel_profile_management import archive_profile_entry_version


router = APIRouter(prefix="/personnel-profiles", tags=["Dijital Personel Kartı"])
_ALLOWED_ENTRY_TYPES = {"contacts", "competencies", "experiences"}


def _require_management_active(company_id: int) -> None:
    if not personnel_profile_card_active(company_id):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "personnel_profile_disabled",
                "message": (
                    "Dijital Personel Kartı bu işyeri için kapalıdır. "
                    "Mevcut personel işlemleri etkilenmeden devam eder."
                ),
            },
        )


@router.post("/{profile_id}/{entry_type}/{entry_key}/archive")
def archive_profile_entry(
    profile_id: int,
    entry_type: str,
    entry_key: str,
    payload: PersonnelProfileEntryArchive,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """İletişim/yeterlilik/deneyim girdisini yeni arşiv sürümüyle sonlandırır."""

    if entry_type not in _ALLOWED_ENTRY_TYPES:
        raise HTTPException(404, "Profil kayıt türü bulunamadı.")
    try:
        normalized_key = validate_profile_entry_key(entry_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    profile = get_profile_or_404(db, profile_id)
    _require_management_active(profile.company_id)
    try:
        row, created = archive_profile_entry_version(
            db,
            user=user,
            profile_id=profile.id,
            entry_type=entry_type,
            entry_key=normalized_key,
            reason=payload.reason,
        )
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise
    return {
        "created": created,
        "id": row.id,
        "entry_key": row.entry_key,
        "version": row.version,
        "lifecycle_status": row.lifecycle_status,
    }


router.include_router(documents_router)
