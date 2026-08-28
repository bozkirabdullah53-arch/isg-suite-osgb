"""Live synchronization for published remote-training catalog video changes.

The central catalog historically materialized immutable company snapshots. That
is correct for audit/history, but it also meant an OSGB administrator could
replace a catalog video while employees with an existing assignment continued
to see the old copied file.

This additive runtime integration keeps historical rows and progress records,
while moving the *current* company video pointer to the newly published catalog
revision. Catalog sections are linked to company snapshot sections by a stable
source identity; mutable ``order_index`` is never used as identity. Published-
video deletion is a logical removal so old progress/audit evidence is preserved.
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import remote_training as remote_api
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.models.remote_training import (
    RemoteTrainingAssignment,
    RemoteTrainingCatalogPackage,
    RemoteTrainingCatalogSection,
    RemoteTrainingCatalogVideo,
    RemoteTrainingProgram,
    RemoteTrainingSection,
    RemoteTrainingVideo,
)
from app.models.remote_training_links import RemoteTrainingCatalogSectionLink

logger = logging.getLogger(__name__)
_INSTALLED = False


def _copy_storage_object(store, source_key: str, target_key: str) -> None:
    """Copy one video object without loading large R2 files into Python memory."""
    source_path = store.resolve_local_path(source_key)
    target_path = store.resolve_local_path(target_key)
    if source_path is not None and source_path.is_file() and target_path is not None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)
        return

    client = getattr(store, "_client", None)
    bucket = getattr(store, "bucket", None)
    full_key = getattr(store, "_full_key", None)
    if client is not None and bucket and callable(full_key):
        client.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": full_key(source_key)},
            Key=full_key(target_key),
        )
        source_size = store.remote_size(source_key)
        target_size = store.remote_size(target_key)
        if source_size is None or target_size != source_size:
            try:
                store.delete(target_key)
            except Exception:
                logger.exception("Boyutu doğrulanamayan canlı video kopyası temizlenemedi: %s", target_key)
            raise RuntimeError("Canlı video kopyasının uzak depolama boyutu doğrulanamadı.")
        return

    # Development/local compatibility fallback. Production R2 uses the
    # server-side copy path above, so large files are not buffered here.
    store.put_bytes(target_key, store.get_bytes(source_key))


def _cleanup_copied_keys(store, keys: list[str]) -> None:
    for key in keys:
        try:
            store.delete(key)
        except Exception:
            logger.exception("Başarısız canlı video senkronu sonrası nesne temizlenemedi: %s", key)


def _programs_for_catalog_package(
    db: Session, package_id: int
) -> list[RemoteTrainingProgram]:
    return list(
        db.scalars(
            select(RemoteTrainingProgram).where(
                RemoteTrainingProgram.source_catalog_package_id == package_id,
                RemoteTrainingProgram.status != "archived",
            )
        ).all()
    )


def _norm_title(value: str | None) -> str:
    return " ".join(str(value or "").split()).casefold()


def _linked_program_section(
    db: Session,
    *,
    program_id: int,
    catalog_section_id: int,
) -> RemoteTrainingSection | None:
    link = db.scalar(
        select(RemoteTrainingCatalogSectionLink).where(
            RemoteTrainingCatalogSectionLink.program_id == program_id,
            RemoteTrainingCatalogSectionLink.catalog_section_id == catalog_section_id,
        )
    )
    if link is None:
        return None
    return db.get(RemoteTrainingSection, link.program_section_id)


def _unique_program_section_by_title(
    db: Session,
    *,
    program_id: int,
    title: str,
) -> RemoteTrainingSection | None:
    wanted = _norm_title(title)
    if not wanted:
        return None
    rows = list(
        db.scalars(
            select(RemoteTrainingSection)
            .where(RemoteTrainingSection.program_id == program_id)
            .order_by(RemoteTrainingSection.id)
        ).all()
    )
    matches = [row for row in rows if _norm_title(row.title) == wanted]
    return matches[0] if len(matches) == 1 else None


def _record_section_link(
    db: Session,
    *,
    program: RemoteTrainingProgram,
    package: RemoteTrainingCatalogPackage,
    catalog_section: RemoteTrainingCatalogSection,
    section: RemoteTrainingSection,
) -> RemoteTrainingCatalogSectionLink:
    existing = db.scalar(
        select(RemoteTrainingCatalogSectionLink).where(
            RemoteTrainingCatalogSectionLink.program_id == program.id,
            RemoteTrainingCatalogSectionLink.catalog_section_id == catalog_section.id,
        )
    )
    if existing is not None:
        if existing.program_section_id != section.id:
            raise HTTPException(
                409,
                "Eğitim bölümünün katalog bağlantısı tutarsız; yanlış videoya dokunulmadı.",
            )
        return existing

    occupied = db.scalar(
        select(RemoteTrainingCatalogSectionLink).where(
            RemoteTrainingCatalogSectionLink.program_section_id == section.id
        )
    )
    if occupied is not None and occupied.catalog_section_id != catalog_section.id:
        raise HTTPException(
            409,
            "Firma eğitim bölümü başka bir katalog bölümüne bağlı; yanlış videoya dokunulmadı.",
        )

    link = RemoteTrainingCatalogSectionLink(
        program_id=program.id,
        program_section_id=section.id,
        catalog_package_id=package.id,
        catalog_section_id=catalog_section.id,
    )
    db.add(link)
    db.flush()
    return link


def ensure_catalog_section_links_for_package(
    db: Session,
    package: RemoteTrainingCatalogPackage,
) -> int:
    """Snapshot stable links before catalog rename/reorder operations.

    Existing materialized sections were copied with the catalog title. A legacy
    row is linked only when that title identifies exactly one section in the
    company program. Ambiguous rows stay unlinked; order_index is intentionally
    never consulted because it is the mutable field being protected against.
    """
    created = 0
    catalog_sections = list(
        db.scalars(
            select(RemTrainingCatalogSection)
            .where(RemoteTrainingCatalogSection.package_id == package.id)
            .order_by(RemoteTrainingCatalogSection.id)
        ).all()
    )
    for program in _programs_for_catalog_package(db, package.id):
        for catalog_section in catalog_sections:
            if _linked_program_section(
                db,
                program_id=program.id,
                catalog_section_id=catalog_section.id,
            ) is not None:
                continue
            section = _unique_program_section_by_title(
                db,
                program_id=program.id,
                title=catalog_section.title,
            )
            if section is None:
                continue
            _record_section_link(
                db,
                program=program,
                package=package,
                catalog_section=catalog_section,
                section=section,
            )
            created += 1
    return created


def _program_section_for_catalog_section(
    db: Session,
    program: RemoteTrainingProgram,
    package: RemoteTrainingCatalogPackage,
    catalog_section: RemoteTrainingCatalogSection,
    *,
    create_if_missing: bool = True,
) -> RemoteTrainingSection | None:
    """Resolve one copied section without ever treating order_index as identity."""
    section = _linked_program_section(
        db,
        program_id=program.id,
        catalog_section_id=catalog_section.id,
    )
    if section is not None:
        return section

    section = _unique_program_section_by_title(
        db,
        program_id=program.id,
        title=catalog_section.title,
    )
    if section is not None:
        _record_section_link(
            db,
            program=program,
            package=package,
            catalog_section=catalog_section,
            section=section,
        )
        return section

    if not create_if_missing:
        return None

    next_order = int(
        db.scalar(
            select(func.max(RemoteTrainingSection.order_index)).where(
                RemoteTrainingSection.program_id == program.id
            )
        )
        or 0
    ) + 1
    desired_order = int(catalog_section.order_index or 0)
    order_index = desired_order if desired_order >= next_order else next_order
    section = RemoteTrainingSection(
        osgb_id=program.osgb_id,
        company_id=program.company_id,
        program_id=program.id,
        sector_code=remote_api.catalog_package_sector_code(package.code),
        title=catalog_section.title,
        description=catalog_section.description,
        order_index=order_index,
        is_required=bool(catalog_section.is_required),
        status="active",
        created_by_id=program.created_by_id,
    )
    db.add(section)
    db.flush()
    _record_section_link(
        db,
        program=program,
        package=package,
        catalog_section=catalog_section,
        section=section,
    )
    return section


def _recalculate_program_assignments(db: Session, program: RemoteTrainingProgram) -> None:
    assignments = list(
        db.scalars(
            select(RemoteTrainingAssignment).where(
                RemoteTrainingAssignment.program_id == program.id,
                RemoteTrainingAssignment.status != "revoked",
            )
        ).all()
    )
    for assignment in assignments:
        remote_api.recalculate_assignment(db, assignment)


def _sync_published_catalog_video(
    db: Session,
    *,
    user: User,
    package: RemoteTrainingCatalogPackage,
    catalog_video: RemoteTrainingCatalogVideo,
) -> tuple[int, list[str]]:
    catalog_section = db.get(RemoteTrainingCatalogSection, catalog_video.section_id)
    if catalog_section is None:
        raise HTTPException(404, "Yeni videonun merkezi katalog bölümü bulunamadı.")

    programs = _programs_for_catalog_package(db, package.id)
    if not programs:
        return 0, []

    store = remote_api._remote_training_video_store()
    copied_keys: list[str] = []
    synced = 0
    now = datetime.utcnow()

    for program in programs:
        section = _program_section_for_catalog_section(db, program, package, catalog_section)
        if section is None:
            raise HTTPException(409, "Firma eğitim bölümü güvenli biçimde eşleştirilemedi.")
        current_rows = list(
            db.scalars(
                select(RemoteTrainingVideo).where(
                    RemoteTrainingVideo.program_id == program.id,
                    RemoteTrainingVideo.section_id == section.id,
                    RemoteTrainingVideo.order_index == catalog_video.order_index,
                    RemoteTrainingVideo.is_current.is_(True),
                )
            ).all()
        )

        already_current = next(
            (
                row
                for row in current_rows
                if int(row.revision_no or 0) == int(catalog_video.revision_no or 0)
                and int(row.file_size_bytes or 0) == int(catalog_video.file_size_bytes or 0)
                and str(row.original_file_name or "") == str(catalog_video.original_file_name or "")
                and row.status == "published"
            ),
            None,
        )
        if already_current is not None:
            program.source_catalog_revision_no = int(package.revision_no or 1)
            continue

        target_key = remote_api.storage_key(
            company_id=program.company_id,
            program_id=program.id,
            prefix="video-live-sync",
            extension=Path(catalog_video.original_file_name or "video.mp4").suffix.lower() or ".mp4",
        )
        _copy_storage_object(store, catalog_video.storage_key, target_key)
        copied_keys.append(target_key)

        previous = current_rows[0] if current_rows else None
        for old in current_rows:
            old.is_current = False
            if old.status != "archived":
                old.status = "unpublished"

        row = RemoteTrainingVideo(
            osgb_id=program.osgb_id,
            company_id=program.company_id,
            program_id=program.id,
            section_id=section.id,
            revision_of_id=previous.id if previous else None,
            title=catalog_video.title,
            description=catalog_video.description,
            learning_objectives=catalog_video.learning_objectives,
            order_index=catalog_video.order_index,
            is_required=bool(catalog_video.is_required),
            revision_no=int(catalog_video.revision_no or 1),
            is_current=True,
            status="published",
            original_file_name=catalog_video.original_file_name,
            content_type=catalog_video.content_type,
            file_size_bytes=catalog_video.file_size_bytes,
            duration_seconds=catalog_video.duration_seconds,
            width=catalog_video.width,
            height=catalog_video.height,
            codec=catalog_video.codec,
            storage_key=target_key,
            published_at=now,
            created_by_id=user.id,
        )
        db.add(row)
        db.flush()

        program.source_catalog_revision_no = int(package.revision_no or 1)
        program.revision_no = int(program.revision_no or 0) + 1
        remote_api.recalculate_program_duration(db, program.id)
        _recalculate_program_assignments(db, program)
        remote_api.audit(
            db,
            company_id=program.company_id,
            user=user,
            action="catalog_video_live_synced",
            entity_type="video",
            entity_id=row.id,
            details={
                "catalog_video_id": catalog_video.id,
                "catalog_package_id": package.id,
                "catalog_section_id": catalog_section.id,
                "program_section_id": section.id,
                "revision_no": catalog_video.revision_no,
                "replaced_video_id": previous.id if previous else None,
            },
        )
        synced += 1

    return synced, copied_keys


def _deactivate_catalog_video_in_programs(
    db: Session,
    *,
    user: User,
    package: RemoteTrainingCatalogPackage,
    catalog_video: RemoteTrainingCatalogVideo,
) -> int:
    catalog_section = db.get(RemoteTrainingCatalogSection, catalog_video.section_id)
    if catalog_section is None:
        return 0

    changed = 0
    for program in _programs_for_catalog_package(db, package.id):
        section = _program_section_for_catalog_section(
            db,
            program,
            package,
            catalog_section,
            create_if_missing=False,
        )
        if section is None:
            logger.warning(
                "Catalog video removal skipped unresolved legacy section: program_id=%s catalog_section_id=%s",
                program.id,
                catalog_section.id,
            )
            continue
        rows = list(
            db.scalars(
                select(RemoteTrainingVideo).where(
                    RemoteTrainingVideo.program_id == program.id,
                    RemoteTrainingVideo.section_id == section.id,
                    RemoteTrainingVideo.order_index == catalog_video.order_index,
                    RemoteTrainingVideo.is_current.is_(True),
                )
            ).all()
        )
        if not rows:
            continue
        for row in rows:
            row.is_current = False
            row.status = "archived"
            row.archived_at = datetime.utcnow()
        program.source_catalog_revision_no = int(package.revision_no or 1)
        program.revision_no = int(program.revision_no or 0) + 1
        remote_api.recalculate_program_duration(db, program.id)
        _recalculate_program_assignments(db, program)
        remote_api.audit(
            db,
            company_id=program.company_id,
            user=user,
            action="catalog_video_live_removed",
            entity_type="video",
            entity_id=rows[0].id,
            details={
                "catalog_video_id": catalog_video.id,
                "catalog_package_id": package.id,
                "catalog_section_id": catalog_section.id,
                "program_section_id": section.id,
            },
        )
        changed += 1
    return changed


def publish_catalog_video_live(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Publish a catalog video and atomically move active company copies to it."""
    video = remote_api._catalog_video_for_content_manager(db, user, video_id)
    if video.status != "ready_for_review":
        raise HTTPException(409, "Video yalnızca incelemeye hazır durumdayken yayımlanabilir.")
    if not video.duration_seconds or not video.storage_key:
        raise HTTPException(409, "Video işleme süresi veya güvenli depolama kaydı eksik.")

    package = remote_api._catalog_content_package_for_manager(db, user, video.package_id)
    if package.status == "archived":
        raise HTTPException(409, "Arşivlenmiş pakete video yayımlanamaz.")

    copied_keys: list[str] = []
    store = remote_api._remote_training_video_store()
    try:
        if video.revision_of_id is not None:
            current = list(
                db.scalars(
                    select(RemoteTrainingCatalogVideo).where(
                        RemoteTrainingCatalogVideo.package_id == video.package_id,
                        RemoteTrainingCatalogVideo.section_id == video.section_id,
                        RemoteTrainingCatalogVideo.is_current.is_(True),
                        RemoteTrainingCatalogVideo.id != video.id,
                        RemoteTrainingCatalogVideo.status.in_(remote_api.REVISIONABLE_VIDEO_STATUSES),
                    )
                ).all()
            )
            for old in current:
                old.is_current = False
                old.status = "unpublished"

        video.is_current = True
        video.status = "published"
        video.published_at = datetime.utcnow()
        if package.status == "published":
            package.revision_no = int(package.revision_no or 0) + 1

        synced, copied_keys = _sync_published_catalog_video(
            db,
            user=user,
            package=package,
            catalog_video=video,
        )
        remote_api.recalculate_catalog_package_duration(db, video.package_id)
        remote_api._commit(db, "Merkezi video yayımlanamadı; firma eğitimleri güncellenmedi.")
        result = remote_api._catalog_video_output(video)
        result["live_synced_program_count"] = synced
        result["employees_use_current_revision"] = True
        return result
    except HTTPException:
        db.rollback()
        _cleanup_copied_keys(store, copied_keys)
        raise
    except Exception as exc:
        db.rollback()
        _cleanup_copied_keys(store, copied_keys)
        logger.exception("Katalog videosu firma eğitimlerine canlı senkronlanamadı: video_id=%s", video_id)
        raise HTTPException(
            503,
            "Yeni video çalışan eğitimlerine güvenli biçimde aktarılamadı; eski çalışan videoları korunmuştur. Tekrar deneyin.",
        ) from exc


def delete_catalog_video_live(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete drafts physically; remove published videos logically and live-sync removal."""
    video = remote_api._catalog_video_for_content_manager(db, user, video_id)
    package = remote_api._catalog_content_package_for_manager(db, user, video.package_id)
    if package.status == "archived":
        raise HTTPException(409, "Arşivlenmiş pakete ait video silinemez.")

    if video.status not in {"published", "unpublished"}:
        return remote_api.delete_catalog_video(video_id=video_id, db=db, user=user)

    video.status = "archived"
    video.is_current = False
    video.archived_at = datetime.utcnow()
    if package.status == "published":
        package.revision_no = int(package.revision_no or 0) + 1

    removed = _deactivate_catalog_video_in_programs(
        db,
        user=user,
        package=package,
        catalog_video=video,
    )
    remote_api.recalculate_catalog_package_duration(db, package.id)
    remote_api._commit(db, "Yayımlanmış video eğitimden kaldırılamadı.")
    return {
        "deleted": True,
        "id": video.id,
        "historical_record_preserved": True,
        "storage_cleanup_pending": False,
        "live_removed_program_count": removed,
        "message": "Video aktif eğitimden kaldırıldı; eski kayıt ve izleme geçmişi denetim için korundu.",
    }


def _replace_route(path_suffix: str, method: str, endpoint) -> bool:
    method = method.upper()
    for route in remote_api.router.routes:
        route_path = str(getattr(route, "path", "") or "")
        methods = set(getattr(route, "methods", set()) or set())
        if route_path.endswith(path_suffix) and method in methods:
            route.endpoint = endpoint
            return True
    return False


def install_remote_training_live_video_sync() -> dict[str, Any]:
    """Replace only catalog publish/delete handlers before main includes the router."""
    global _INSTALLED
    if _INSTALLED:
        return {"installed": True, "already_installed": True}

    publish_patched = _replace_route(
        "/catalog/videos/{video_id}/publish",
        "POST",
        publish_catalog_video_live,
    )
    delete_patched = _replace_route(
        "/catalog/videos/{video_id}",
        "DELETE",
        delete_catalog_video_live,
    )
    if not publish_patched or not delete_patched:
        raise RuntimeError("Uzaktan eğitim video yayın/silme route'ları bulunamadı.")

    _INSTALLED = True
    return {
        "installed": True,
        "already_installed": False,
        "publish_patched": publish_patched,
        "delete_patched": delete_patched,
    }
