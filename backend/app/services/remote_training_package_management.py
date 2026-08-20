"""Additive edit/delete controls for OSGB-owned remote-training catalog content.

Shared catalog packages remain protected. OSGB-owned packages can be edited or
deleted by the OSGB content manager. When a package has already been materialized
for a company, deleting the catalog row detaches only the source link; the
company/employee snapshot, progress, exams, and certificates remain untouched.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.api import remote_training as remote_api
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.models.remote_training import (
    RemoteTrainingCatalogPackage,
    RemoteTrainingCatalogSection,
    RemoteTrainingCatalogVideo,
    RemoteTrainingProgram,
)

logger = logging.getLogger(__name__)
_INSTALLED = False


class RemoteCatalogPackageMetadataUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=220)
    description: str | None = Field(default=None, max_length=5000)


class RemoteCatalogSectionMetadataUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    is_required: bool | None = None

class RemoteCatalogSectionReorder(BaseModel):
    """Complete ordered list of sections for one catalog package."""

    model_config = ConfigDict(extra="forbid")

    section_ids: list[int] = Field(min_length=1, max_length=2000)


def _private_package(
    db: Session, user: User, package_id: int
) -> RemoteTrainingCatalogPackage:
    package = remote_api._catalog_content_package_for_manager(db, user, package_id)
    if package.osgb_id is None:
        raise HTTPException(
            409,
            "Ortak hazır paket doğrudan değiştirilemez veya silinemez. Önce OSGB özel kopyasını oluşturun.",
        )
    return package


def _clean_title(value: str | None) -> str:
    clean = " ".join(str(value or "").split())
    if len(clean) < 3:
        raise HTTPException(422, "Eğitim paketi adı en az 3 karakter olmalıdır.")
    return clean


def _clean_section_code(value: str | None) -> str:
    clean = " ".join(str(value or "").split()).upper()
    if len(clean) < 2:
        raise HTTPException(422, "Bölüm kodu en az 2 karakter olmalıdır.")
    return clean


def _clean_section_title(value: str | None) -> str:
    clean = " ".join(str(value or "").split())
    if len(clean) < 2:
        raise HTTPException(422, "Bölüm adı en az 2 karakter olmalıdır.")
    return clean


def _assert_unique_package_title(
    db: Session,
    package: RemoteTrainingCatalogPackage,
    title: str,
) -> None:
    duplicate = db.scalar(
        select(RemoteTrainingCatalogPackage.id).where(
            RemoteTrainingCatalogPackage.osgb_id == package.osgb_id,
            RemoteTrainingCatalogPackage.id != package.id,
            func.lower(RemoteTrainingCatalogPackage.title) == title.lower(),
        )
    )
    if duplicate:
        raise HTTPException(409, "Bu OSGB içinde aynı adla başka bir eğitim paketi bulunuyor.")


def _cleanup_storage(keys: list[str]) -> bool:
    if not keys:
        return False
    pending = False
    store = remote_api.get_object_store()
    for key in keys:
        try:
            store.delete(key)
        except Exception:
            pending = True
            logger.exception("Silinen katalog video nesnesi temizlenemedi: %s", key)
    return pending


def update_catalog_package_metadata(
    package_id: int,
    payload: RemoteCatalogPackageMetadataUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    package = _private_package(db, user, package_id)
    if package.status == "archived":
        raise HTTPException(
            409,
            "Arşivlenmiş paketin bilgileri değiştirilemez. Önce paketi düzenlemeye açın.",
        )

    fields = payload.model_fields_set
    if not fields:
        raise HTTPException(422, "Değiştirilecek paket bilgisi gönderilmedi.")

    if "title" in fields:
        title = _clean_title(payload.title)
        _assert_unique_package_title(db, package, title)
        package.title = title
    if "description" in fields:
        package.description = str(payload.description or "").strip() or None

    package.revision_no = int(package.revision_no or 0) + 1
    remote_api._commit(db, "Eğitim paketi bilgileri güncellenemedi.")
    db.refresh(package)
    return remote_api._catalog_package_output(db, package, detail=True)


def delete_catalog_package_safely(
    package_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    package = _private_package(db, user, package_id)

    materialized_count = int(
        db.scalar(
            select(func.count(RemoteTrainingProgram.id)).where(
                RemoteTrainingProgram.source_catalog_package_id == package.id
            )
        )
        or 0
    )
    # Materialized programs own their copied sections, videos, questions and
    # employee progress. Detach the optional catalog source link before removing
    # the catalog row so historical company records stay valid and traceable.
    if materialized_count:
        db.execute(
            update(RemoteTrainingProgram)
            .where(RemoteTrainingProgram.source_catalog_package_id == package.id)
            .values(source_catalog_package_id=None)
        )

    storage_keys = list(
        db.scalars(
            select(RemoteTrainingCatalogVideo.storage_key).where(
                RemoteTrainingCatalogVideo.package_id == package.id
            )
        ).all()
    )
    title = package.title
    db.execute(
        delete(RemoteTrainingCatalogVideo).where(
            RemoteTrainingCatalogVideo.package_id == package.id
        )
    )
    db.execute(
        delete(RemoteTrainingCatalogSection).where(
            RemoteTrainingCatalogSection.package_id == package.id
        )
    )
    db.delete(package)
    remote_api._commit(db, "Eğitim paketi silinemedi.")

    return {
        "deleted": True,
        "id": package_id,
        "title": title,
        "history_preserved": bool(materialized_count),
        "materialized_program_count": materialized_count,
        "storage_cleanup_pending": _cleanup_storage(storage_keys),
    }


def update_catalog_section_metadata(
    section_id: int,
    payload: RemoteCatalogSectionMetadataUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = remote_api._catalog_section_for_content_manager(db, user, section_id)
    package = _private_package(db, user, section.package_id)
    if package.status == "archived":
        raise HTTPException(409, "Arşivlenmiş paketin içeriği değiştirilemez. Önce paketi düzenlemeye açın.")

    fields = payload.model_fields_set
    if not fields:
        raise HTTPException(422, "Değiştirilecek bölüm bilgisi gönderilmedi.")

    if "code" in fields:
        code = _clean_section_code(payload.code)
        duplicate = db.scalar(
            select(RemoteTrainingCatalogSection.id).where(
                RemoteTrainingCatalogSection.package_id == package.id,
                RemoteTrainingCatalogSection.id != section.id,
                func.lower(RemoteTrainingCatalogSection.code) == code.lower(),
            )
        )
        if duplicate:
            raise HTTPException(409, "Bu paket içinde aynı bölüm kodu zaten kullanılıyor.")
        section.code = code
    if "title" in fields:
        section.title = _clean_section_title(payload.title)
    if "description" in fields:
        section.description = str(payload.description or "").strip() or None
    if "is_required" in fields and payload.is_required is not None:
        section.is_required = bool(payload.is_required)

    package.revision_no = int(package.revision_no or 0) + 1
    remote_api._commit(db, "Eğitim bölümü güncellenemedi.")
    db.refresh(section)
    return remote_api._catalog_section_output(db, section)


def reorder_catalog_sections(
    package_id: int,
    payload: RemoteCatalogSectionReorder,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Persist a complete, validated order for an OSGB-owned catalog package.

    Section rows have a unique (package_id, order_index) constraint. They are
    moved through a temporary negative range first so PostgreSQL and SQLite
    both remain safe when two sections exchange positions.
    """

    package = _private_package(db, user, package_id)
    if package.status == "archived":
        raise HTTPException(
            409,
            "Arşivlenmiş paketin bölümleri sıralanamaz. Önce paketi düzenlemeye açın.",
        )

    requested_ids = [int(section_id) for section_id in payload.section_ids]
    if len(set(requested_ids)) != len(requested_ids):
        raise HTTPException(422, "Bölüm sıralamasında aynı bölüm birden fazla kez gönderilemez.")

    sections = list(
        db.scalars(
            select(RemoteTrainingCatalogSection)
            .where(RemoteTrainingCatalogSection.package_id == package.id)
            .order_by(
                RemoteTrainingCatalogSection.order_index,
                RemoteTrainingCatalogSection.id,
            )
        ).all()
    )
    actual_ids = {int(section.id) for section in sections}
    requested_set = set(requested_ids)
    if requested_set != actual_ids:
        missing = sorted(actual_ids - requested_set)
        unknown = sorted(requested_set - actual_ids)
        details = []
        if missing:
            details.append(f"eksik bölüm kimlikleri: {', '.join(map(str, missing))}")
        if unknown:
            details.append(f"pakete ait olmayan kimlikler: {', '.join(map(str, unknown))}")
        raise HTTPException(
            422,
            "Bölüm sıralaması paketteki tüm bölümleri tam olarak içermelidir"
            + (f" ({'; '.join(details)})." if details else "."),
        )

    current_ids = [int(section.id) for section in sections]
    changed = current_ids != requested_ids
    if changed:
        # Avoid transient unique-key collisions while swapping/reordering rows.
        for section in sections:
            section.order_index = -1_000_000_000 - int(section.id)
        db.flush()

        by_id = {int(section.id): section for section in sections}
        for order_index, section_id in enumerate(requested_ids, start=1):
            by_id[section_id].order_index = order_index

        package.revision_no = int(package.revision_no or 0) + 1
        remote_api._commit(db, "Bölüm sırası kaydedilemedi.")

    result = remote_api._catalog_package_output(db, package, detail=True)
    result["reordered"] = changed
    return result


def delete_catalog_section_safely(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = remote_api._catalog_section_for_content_manager(db, user, section_id)
    package = _private_package(db, user, section.package_id)
    if package.status == "archived":
        raise HTTPException(409, "Arşivlenmiş paketin bölümü silinemez. Önce paketi düzenlemeye açın.")

    storage_keys = list(
        db.scalars(
            select(RemoteTrainingCatalogVideo.storage_key).where(
                RemoteTrainingCatalogVideo.section_id == section.id
            )
        ).all()
    )
    title = section.title
    db.execute(
        delete(RemoteTrainingCatalogVideo).where(
            RemoteTrainingCatalogVideo.section_id == section.id
        )
    )
    db.delete(section)
    db.flush()
    remote_api.recalculate_catalog_package_duration(db, package.id)
    package.revision_no = int(package.revision_no or 0) + 1
    remote_api._commit(db, "Eğitim bölümü silinemedi.")

    return {
        "deleted": True,
        "id": section_id,
        "title": title,
        "storage_cleanup_pending": _cleanup_storage(storage_keys),
    }


def _route_exists(path_suffix: str, method: str) -> bool:
    method = method.upper()
    for route in remote_api.router.routes:
        route_path = str(getattr(route, "path", "") or "")
        methods = set(getattr(route, "methods", set()) or set())
        if route_path.endswith(path_suffix) and method in methods:
            return True
    return False


def install_remote_training_package_management() -> dict[str, Any]:
    """Register isolated management routes before the main router is included."""
    global _INSTALLED
    if _INSTALLED:
        return {"installed": True, "already_installed": True}

    routes = (
        (
            "/catalog/packages/{package_id}/sections/order",
            reorder_catalog_sections,
            ["PATCH"],
        ),
        (
            "/catalog/packages/{package_id}",
            update_catalog_package_metadata,
            ["PATCH"],
        ),
        (
            "/catalog/packages/{package_id}",
            delete_catalog_package_safely,
            ["DELETE"],
        ),
        (
            "/catalog/sections/{section_id}",
            update_catalog_section_metadata,
            ["PATCH"],
        ),
        (
            "/catalog/sections/{section_id}",
            delete_catalog_section_safely,
            ["DELETE"],
        ),
    )
    added: list[str] = []
    for path, endpoint, methods in routes:
        method = methods[0]
        if _route_exists(path, method):
            continue
        remote_api.router.add_api_route(
            path,
            endpoint,
            methods=methods,
            tags=["Uzaktan Temel İSG Eğitimi"],
        )
        added.append(f"{method} {path}")

    _INSTALLED = True
    return {
        "installed": True,
        "already_installed": False,
        "routes_added": added,
    }

