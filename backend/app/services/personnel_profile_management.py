"""Dijital Personel Kartı yönetim servisleri.

Mevcut sürüm satırlarını değiştirmez veya silmez. Bir iletişim, yeterlilik ya da
deneyim kaydı kaldırıldığında son değerler yeni bir ``archived`` sürüme kopyalanır.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.models.entities import User
from app.models.personnel_profile import (
    PersonnelProfileCompetency,
    PersonnelProfileContact,
    PersonnelProfileExperience,
)
from app.services.audit import add_audit_log
from app.services.personnel_profile_core import (
    get_profile_or_404,
    require_profile_write_role,
)


ProfileEntryType = Literal["contacts", "competencies", "experiences"]

_ENTRY_MODELS: dict[str, type[Any]] = {
    "contacts": PersonnelProfileContact,
    "competencies": PersonnelProfileCompetency,
    "experiences": PersonnelProfileExperience,
}

_COPY_FIELDS: dict[str, tuple[str, ...]] = {
    "contacts": (
        "contact_type",
        "label",
        "contact_value",
        "is_primary",
        "visibility",
        "verification_status",
        "verified_by_id",
        "verified_at",
    ),
    "competencies": (
        "category",
        "name",
        "start_date",
        "end_date",
        "certificate_number",
        "issuing_organization",
        "description",
        "verification_status",
        "approved_by_id",
        "approved_at",
    ),
    "experiences": (
        "organization_name",
        "position",
        "start_date",
        "end_date",
        "employment_type",
        "sector",
        "nace_activity",
        "project_name",
        "professional_summary",
        "responsibilities",
        "visibility",
        "approved_by_id",
        "approved_at",
    ),
}


def _entry_model(entry_type: str) -> type[Any]:
    model = _ENTRY_MODELS.get(str(entry_type or ""))
    if model is None:
        raise HTTPException(404, "Profil kayıt türü bulunamadı.")
    return model


def _latest_entry(
    db: Session,
    *,
    model: type[Any],
    profile_id: int,
    entry_key: str,
) -> Any | None:
    return db.scalar(
        select(model)
        .where(model.profile_id == profile_id, model.entry_key == entry_key)
        .order_by(model.version.desc())
        .limit(1)
    )


def archive_profile_entry_version(
    db: Session,
    *,
    user: User,
    profile_id: int,
    entry_type: ProfileEntryType | str,
    entry_key: str,
    reason: str,
) -> tuple[Any, bool]:
    """Son sürümü kopyalayıp arşiv sürümü oluşturur; fiziksel silme yapmaz."""

    require_profile_write_role(user)
    profile = get_profile_or_404(db, profile_id)
    ensure_company_access(db, user, profile.company_id)
    if profile.status != "active":
        raise HTTPException(409, "Arşivlenmiş profil üzerinde kayıt işlemi yapılamaz.")

    normalized_type = str(entry_type or "")
    model = _entry_model(normalized_type)
    latest = _latest_entry(
        db,
        model=model,
        profile_id=profile.id,
        entry_key=entry_key,
    )
    if latest is None:
        raise HTTPException(404, "Arşivlenecek profil kaydı bulunamadı.")
    if latest.lifecycle_status == "archived":
        return latest, False

    copied = {
        field: getattr(latest, field)
        for field in _COPY_FIELDS[normalized_type]
    }
    row = model(
        profile_id=profile.id,
        company_id=profile.company_id,
        entry_key=latest.entry_key,
        version=int(latest.version) + 1,
        supersedes_id=latest.id,
        lifecycle_status="archived",
        change_reason=reason,
        created_by_id=user.id,
        **copied,
    )
    db.add(row)
    db.flush()
    add_audit_log(
        db,
        user=user,
        action=f"personnel_profile_{normalized_type}_archived",
        entity_type=f"personnel_profile_{normalized_type}",
        entity_id=str(row.id),
        module="personnel_profile",
        description=(
            "Profil girdisi fiziksel silinmeden arşiv sürümüyle sonlandırıldı; "
            f"profile_id={profile.id}, entry_key={latest.entry_key}, version={row.version}."
        ),
    )
    return row, True
