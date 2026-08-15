"""Additive OSGB-scoped custom package support for remote training.

The existing remote-training implementation remains untouched.  This installer
adds one create endpoint, broadens only the package-list query to include
tenant-owned custom packages, and maps custom package codes back to the
existing vetted sector question packs and rollout gates.
"""
from __future__ import annotations

import secrets
from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api import remote_training as remote_api
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import remote_training as remote_models
from app.models.entities import User, UserRole
from app.models.remote_training import (
    REMOTE_CATALOG_PACKAGE_SPECS,
    REMOTE_TRAINING_TYPE,
    RemoteTrainingCatalogPackage,
)
from app.services import remote_training as remote_service


CUSTOM_PACKAGE_PREFIX = "custom--"

# A custom curriculum may only reuse a sector whose reviewed 10-question pack
# and strict rollout code already exist.  This deliberately fails closed for
# "foundry" until a dedicated reviewed package is introduced.
CUSTOM_SECTOR_BASE_PACKAGE = {
    "common": "common-basic-ohs",
    "construction": "construction-ohs",
    "battery": "battery-production-ohs",
    "metal": "metal-machine-ohs",
    "logistics": "logistics-warehouse-transport-ohs",
    "food": "food-production-ohs",
    "chemical": "chemical-paint-production-ohs",
    "mining": "open-mine-quarry-aggregate-ohs",
    "road": "road-asphalt-infrastructure-ohs",
    "office": "office-general-ohs",
    "working_at_height": "working-at-height-ohs",
}
CUSTOM_PACKAGE_SECTOR_CODES = frozenset(CUSTOM_SECTOR_BASE_PACKAGE)

_ORIGINAL_MODEL_CATALOG_SECTOR = remote_models.catalog_package_sector_code
_ORIGINAL_API_AUTO_EXAM = remote_api.automatic_exam_items_for_package
_ORIGINAL_API_POLICY_ACTIVE = remote_api.remote_basic_ohs_strict_policy_active
_ORIGINAL_PACKAGE_OUTPUT = remote_api._catalog_package_output

_INSTALLED = False


class RemoteCustomCatalogPackageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=220)
    sector_code: str = Field(min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        clean = " ".join(str(value or "").split())
        if len(clean) < 3:
            raise ValueError("Eğitim paketi adı en az 3 karakter olmalıdır.")
        return clean

    @field_validator("sector_code")
    @classmethod
    def normalize_sector_code(cls, value: str) -> str:
        return str(value or "").strip().lower()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        clean = str(value or "").strip()
        return clean or None


def custom_package_sector_code(package_code: str | None) -> str | None:
    normalized = str(package_code or "").strip().lower()
    if not normalized.startswith(CUSTOM_PACKAGE_PREFIX):
        return None
    parts = normalized.split("--", 2)
    if len(parts) != 3:
        return None
    sector_code = parts[1].strip()
    return sector_code if sector_code in CUSTOM_PACKAGE_SECTOR_CODES else None


def custom_package_base_code(package_code: str | None) -> str | None:
    sector_code = custom_package_sector_code(package_code)
    if not sector_code:
        return None
    return CUSTOM_SECTOR_BASE_PACKAGE[sector_code]


def catalog_package_sector_code_with_custom(package_code: str | None) -> str:
    sector_code = custom_package_sector_code(package_code)
    if sector_code:
        return sector_code
    return _ORIGINAL_MODEL_CATALOG_SECTOR(package_code)


def automatic_exam_items_for_package_with_custom(
    package_code: str | None,
) -> list[dict[str, Any]]:
    base_code = custom_package_base_code(package_code)
    return _ORIGINAL_API_AUTO_EXAM(base_code or package_code)


def strict_policy_active_with_custom(
    package_code: str | None, company_id: int | None = None
) -> bool:
    base_code = custom_package_base_code(package_code)
    return _ORIGINAL_API_POLICY_ACTIVE(base_code or package_code, company_id)


def catalog_package_output_with_custom(
    db: Session,
    package: RemoteTrainingCatalogPackage,
    *,
    detail: bool = False,
) -> dict[str, Any]:
    result = _ORIGINAL_PACKAGE_OUTPUT(db, package, detail=detail)
    sector_code = custom_package_sector_code(package.code)
    if not sector_code:
        result["is_custom"] = False
        return result

    # The browser already knows how to label/distribute the vetted base package
    # codes.  Keep the real custom code server-side for isolation and immutable
    # snapshots, but expose the compatible base code to the existing UI.
    result["catalog_code"] = package.code
    result["code"] = CUSTOM_SECTOR_BASE_PACKAGE[sector_code]
    result["sector_code"] = sector_code
    result["is_custom"] = True
    result["is_shared"] = False
    return result


def _next_custom_code(db: Session, scope: int, sector_code: str) -> str:
    for _ in range(12):
        candidate = f"{CUSTOM_PACKAGE_PREFIX}{sector_code}--{secrets.token_hex(5)}"
        exists = db.scalar(
            select(RemoteTrainingCatalogPackage.id).where(
                RemoteTrainingCatalogPackage.osgb_id == scope,
                RemoteTrainingCatalogPackage.code == candidate,
            )
        )
        if not exists:
            return candidate
    raise HTTPException(500, "Yeni eğitim paketi için benzersiz kayıt kodu üretilemedi.")


def _assert_unique_active_title(
    db: Session, scope: int, title: str
) -> None:
    rows = list(
        db.scalars(
            select(RemoteTrainingCatalogPackage).where(
                RemoteTrainingCatalogPackage.osgb_id == scope,
                RemoteTrainingCatalogPackage.status != "archived",
            )
        ).all()
    )
    wanted = title.casefold()
    if any(str(row.title or "").strip().casefold() == wanted for row in rows):
        raise HTTPException(
            409,
            "Bu OSGB içinde aynı adla aktif bir eğitim paketi zaten bulunuyor.",
        )


def create_custom_catalog_package(
    payload: RemoteCustomCatalogPackageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    remote_api.require_feature()
    remote_api._assert_catalog_content_editor(db, user)
    scope = remote_api._catalog_scope(db, user)
    if scope is None or user.role == UserRole.GLOBAL_ADMIN:
        raise HTTPException(
            409,
            "Yeni özel eğitim paketi yalnızca bir OSGB yöneticisi kapsamında oluşturulabilir.",
        )

    sector_code = payload.sector_code
    if sector_code not in CUSTOM_PACKAGE_SECTOR_CODES:
        raise HTTPException(
            422,
            "Bu kategori için doğrulanmış 10 soruluk sektör soru paketi henüz hazır değil.",
        )

    remote_api.assert_osgb_subscription_access(db, user, scope)
    _assert_unique_active_title(db, scope, payload.title)

    package = RemoteTrainingCatalogPackage(
        osgb_id=scope,
        code=_next_custom_code(db, scope, sector_code),
        title=payload.title,
        description=payload.description,
        training_type=REMOTE_TRAINING_TYPE,
        total_duration_seconds=0,
        requires_final_exam=True,
        completion_threshold_percent=100,
        passing_score=70,
        attempt_limit=3,
        policy_mode="strict",
        sequence_enforced=True,
        exam_gate_enforced=True,
        status="draft",
        revision_no=1,
        created_by_id=user.id,
    )
    db.add(package)
    db.flush()
    remote_api._commit(db, "Yeni eğitim paketi oluşturulamadı.")
    db.refresh(package)
    return remote_api._catalog_package_output(db, package, detail=True)


def list_catalog_packages_with_custom(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Preserve the central catalog and append only this OSGB's custom packages."""
    remote_api.require_feature()
    remote_api._manager(user)
    remote_api._ensure_catalog_seed(db, user)
    scope = remote_api._catalog_scope(db, user)
    if scope is not None:
        remote_api.assert_osgb_subscription_access(db, user, scope)

    allowed_codes = tuple(spec["code"] for spec in REMOTE_CATALOG_PACKAGE_SPECS)
    if user.role == UserRole.GLOBAL_ADMIN:
        stmt = select(RemoteTrainingCatalogPackage).where(
            RemoteTrainingCatalogPackage.osgb_id.is_(None),
            RemoteTrainingCatalogPackage.code.in_(allowed_codes),
        )
    else:
        stmt = select(RemoteTrainingCatalogPackage).where(
            or_(
                and_(
                    RemoteTrainingCatalogPackage.osgb_id.is_(None),
                    RemoteTrainingCatalogPackage.code.in_(allowed_codes),
                ),
                RemoteTrainingCatalogPackage.osgb_id == scope,
            )
        )

    rows = list(
        db.scalars(
            stmt.order_by(
                RemoteTrainingCatalogPackage.created_at,
                RemoteTrainingCatalogPackage.id,
            )
        ).all()
    )

    if scope is None:
        shared = {row.code: row for row in rows if row.osgb_id is None}
        ordered = [shared[code] for code in allowed_codes if code in shared]
    else:
        own_known = {
            row.code: row
            for row in rows
            if row.osgb_id == scope and row.code in allowed_codes
        }
        shared = {
            row.code: row
            for row in rows
            if row.osgb_id is None and row.code in allowed_codes
        }
        ordered = [
            own_known.get(code) or shared.get(code)
            for code in allowed_codes
        ]
        ordered = [row for row in ordered if row is not None]

        custom_rows = [
            row
            for row in rows
            if row.osgb_id == scope and row.code not in allowed_codes
        ]
        custom_rows.sort(key=lambda row: (row.created_at, row.id))
        ordered.extend(custom_rows)

    return [remote_api._catalog_package_output(db, row) for row in ordered]


def _replace_get_endpoint(path_suffix: str, endpoint) -> bool:
    for route in remote_api.router.routes:
        route_path = str(getattr(route, "path", "") or "")
        methods = set(getattr(route, "methods", set()) or set())
        if route_path.endswith(path_suffix) and "GET" in methods:
            route.endpoint = endpoint
            dependant = getattr(route, "dependant", None)
            if dependant is not None:
                dependant.call = endpoint
            return True
    return False


def _post_create_route_exists() -> bool:
    for route in remote_api.router.routes:
        route_path = str(getattr(route, "path", "") or "")
        methods = set(getattr(route, "methods", set()) or set())
        if route_path.endswith("/catalog/packages") and "POST" in methods:
            return True
    return False


def install_remote_training_custom_packages() -> dict[str, object]:
    """Install the additive extension before ``app.include_router`` runs."""
    global _INSTALLED
    if _INSTALLED:
        return {
            "installed": True,
            "already_installed": True,
            "supported_sector_codes": sorted(CUSTOM_PACKAGE_SECTOR_CODES),
        }

    remote_models.catalog_package_sector_code = catalog_package_sector_code_with_custom
    remote_service.catalog_package_sector_code = catalog_package_sector_code_with_custom
    remote_api.catalog_package_sector_code = catalog_package_sector_code_with_custom

    remote_service.automatic_exam_items_for_package = automatic_exam_items_for_package_with_custom
    remote_api.automatic_exam_items_for_package = automatic_exam_items_for_package_with_custom

    remote_service.remote_basic_ohs_strict_policy_active = strict_policy_active_with_custom
    remote_api.remote_basic_ohs_strict_policy_active = strict_policy_active_with_custom

    remote_api._catalog_package_output = catalog_package_output_with_custom
    remote_api.list_catalog_packages = list_catalog_packages_with_custom

    replaced = _replace_get_endpoint(
        "/catalog/packages",
        list_catalog_packages_with_custom,
    )
    if not replaced:
        raise RuntimeError("Uzaktan eğitim paket liste rotası bulunamadı.")

    if not _post_create_route_exists():
        remote_api.router.add_api_route(
            "/catalog/packages",
            create_custom_catalog_package,
            methods=["POST"],
            status_code=201,
            tags=["Uzaktan Temel İSG Eğitimi"],
        )

    _INSTALLED = True
    return {
        "installed": True,
        "already_installed": False,
        "list_route_replaced": True,
        "create_route_added": True,
        "supported_sector_codes": sorted(CUSTOM_PACKAGE_SECTOR_CODES),
    }
