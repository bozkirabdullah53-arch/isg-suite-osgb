"""Administrator-only NACE classification and legacy consistency reports."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import User, UserRole
from app.services.training_nace_registry import (
    build_registry,
    legacy_training_report,
    materialize_registry,
    normalize_nace_code,
    registry_report,
)

router = APIRouter(prefix="/training-consistency", tags=["Eğitim Tutarlılığı"])
ADMIN = (UserRole.GLOBAL_ADMIN,)


@router.get("/catalog/report")
def catalog_report(
    q: str | None = Query(default=None, max_length=140),
    status: str | None = Query(
        default=None,
        pattern=r"^(mapped|review_required|blocked)$",
    ),
    hazard_class: str | None = Query(
        default=None,
        pattern=r"^(Az Tehlikeli|Tehlikeli|Çok Tehlikeli)$",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    _user: User = Depends(require_roles(*ADMIN)),
):
    report = registry_report(include_entries=True)
    entries = report.pop("entries")
    needle = str(q or "").strip().casefold()
    if needle:
        entries = [
            item
            for item in entries
            if needle
            in " ".join(
                str(item.get(key) or "")
                for key in (
                    "nace_code",
                    "description",
                    "main_sector_name",
                    "profile_code",
                    "profile_name",
                )
            ).casefold()
        ]
    if status:
        entries = [item for item in entries if item["mapping_status"] == status]
    if hazard_class:
        entries = [item for item in entries if item["hazard_class"] == hazard_class]
    total = len(entries)
    return {
        **report,
        "filtered_total": total,
        "offset": offset,
        "limit": limit,
        "entries": entries[offset : offset + limit],
    }


@router.get("/catalog/{nace_code}")
def catalog_entry(
    nace_code: str,
    _user: User = Depends(require_roles(*ADMIN)),
):
    normalized = normalize_nace_code(nace_code)
    if not normalized:
        raise HTTPException(422, "Geçerli altılı NACE kodu girilmelidir.")
    row = next((item for item in build_registry() if item.nace_code == normalized), None)
    if not row:
        raise HTTPException(404, "NACE kodu katalogda bulunamadı.")
    return row.payload()


@router.post("/catalog/materialize", status_code=201)
def materialize_catalog(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN)),
):
    """Create an immutable candidate catalog version; never auto-activate it."""
    try:
        result = materialize_registry(db, created_by_id=user.id)
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(422, "NACE katalog sürümü oluşturulamadı.") from exc


@router.get("/catalog/versions")
def catalog_versions(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*ADMIN)),
):
    rows = db.execute(
        text("""
            SELECT id, version_code, content_hash, source_label, source_url,
                   status, entry_count, created_by_id, created_at,
                   activated_by_id, activated_at
            FROM training_nace_catalog_versions
            ORDER BY created_at DESC, id DESC
        """)
    ).mappings().all()
    return [dict(row) for row in rows]


@router.get("/legacy-trainings/report")
def legacy_report(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*ADMIN)),
):
    return legacy_training_report(db)
