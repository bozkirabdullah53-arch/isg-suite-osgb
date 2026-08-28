from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def _db() -> Session:
    from app.core.database import Base
    from app.models import entities  # noqa: F401
    from app.models import remote_training  # noqa: F401
    from app.models import remote_training_links  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _fixture_rows(db: Session):
    from app.models.remote_training import (
        RemoteTrainingCatalogPackage,
        RemoteTrainingCatalogSection,
        RemoteTrainingCatalogVideo,
        RemoteTrainingProgram,
        RemoteTrainingSection,
        RemoteTrainingVideo,
    )

    package = RemoteTrainingCatalogPackage(
        osgb_id=77,
        code="battery-production-ohs",
        title="Akü-Batarya",
        status="published",
        revision_no=5,
    )
    db.add(package)
    db.flush()

    catalog_a = RemoteTrainingCatalogSection(
        package_id=package.id,
        code="AKU-01",
        title="Bölüm A",
        order_index=1,
        status="active",
        is_required=True,
    )
    catalog_b = RemoteTrainingCatalogSection(
        package_id=package.id,
        code="AKU-02",
        title="Bölüm B",
        order_index=2,
        status="active",
        is_required=True,
    )
    db.add_all([catalog_a, catalog_b])
    db.flush()

    program = RemoteTrainingProgram(
        osgb_id=77,
        company_id=909,
        source_catalog_package_id=package.id,
        source_catalog_code=package.code,
        source_catalog_revision_no=package.revision_no,
        title=package.title,
        status="published",
        revision_no=1,
        created_by_id=1,
    )
    db.add(program)
    db.flush()

    section_a = RemoteTrainingSection(
        osgb_id=77,
        company_id=909,
        program_id=program.id,
        sector_code="battery",
        title="Bölüm A",
        order_index=1,
        is_required=True,
        status="active",
        created_by_id=1,
    )
    section_b = RemoteTrainingSection(
        osgb_id=77,
        company_id=909,
        program_id=program.id,
        sector_code="battery",
        title="Bölüm B",
        order_index=2,
        is_required=True,
        status="active",
        created_by_id=1,
    )
    db.add_all([section_a, section_b])
    db.flush()

    catalog_video = RemoteTrainingCatalogVideo(
        package_id=package.id,
        section_id=catalog_b.id,
        title="B videosu",
        order_index=1,
        revision_no=2,
        is_current=True,
        is_required=True,
        status="published",
        original_file_name="b-v2.mp4",
        content_type="video/mp4",
        file_size_bytes=200,
        duration_seconds=60,
        storage_key="catalog/b-v2.mp4",
        created_by_id=1,
    )
    db.add(catalog_video)
    db.flush()

    video_a = RemoteTrainingVideo(
        osgb_id=77,
        company_id=909,
        program_id=program.id,
        section_id=section_a.id,
        title="A videosu",
        order_index=1,
        revision_no=1,
        is_current=True,
        is_required=True,
        status="published",
        original_file_name="a.mp4",
        content_type="video/mp4",
        file_size_bytes=100,
        duration_seconds=40,
        storage_key="program/a.mp4",
        created_by_id=1,
    )
    video_b = RemoteTrainingVideo(
        osgb_id=77,
        company_id=909,
        program_id=program.id,
        section_id=section_b.id,
        title="B videosu eski",
        order_index=1,
        revision_no=1,
        is_current=True,
        is_required=True,
        status="published",
        original_file_name="b-v1.mp4",
        content_type="video/mp4",
        file_size_bytes=100,
        duration_seconds=50,
        storage_key="program/b-v1.mp4",
        created_by_id=1,
    )
    db.add_all([video_a, video_b])
    db.commit()
    return package, catalog_a, catalog_b, program, section_a, section_b, catalog_video, video_a, video_b


def _reorder_catalog_only(db: Session, catalog_a, catalog_b) -> None:
    # Simulate the bug-producing state: catalog B moved to position 1 while the
    # already materialized company snapshot retains its historical order.
    catalog_a.order_index = -1001
    catalog_b.order_index = -1002
    db.flush()
    catalog_b.order_index = 1
    catalog_a.order_index = 2
    db.commit()


def _patch_side_effects(monkeypatch, sync):
    monkeypatch.setattr(sync.remote_api, "recalculate_program_duration", lambda *_a, **_k: None)
    monkeypatch.setattr(sync.remote_api, "recalculate_assignment", lambda *_a, **_k: None)
    monkeypatch.setattr(sync.remote_api, "audit", lambda *_a, **_k: None)


def test_live_route_rebind_updates_fastapi_dependant_call():
    from app.services import remote_training_live_video_sync as sync
    from app.services import remote_training_route_rebind as rebind

    sync.install_remote_training_live_video_sync()
    rebind.install_remote_training_route_rebind()

    publish_route = next(
        route
        for route in sync.remote_api.router.routes
        if str(getattr(route, "path", "")).endswith("/catalog/videos/{video_id}/publish")
        and "POST" in (getattr(route, "methods", set()) or set())
    )
    delete_route = next(
        route
        for route in sync.remote_api.router.routes
        if str(getattr(route, "path", "")).endswith("/catalog/videos/{video_id}")
        and "DELETE" in (getattr(route, "methods", set()) or set())
    )

    assert publish_route.endpoint is sync.publish_catalog_video_live
    assert publish_route.dependant.call is sync.publish_catalog_video_live
    assert delete_route.endpoint is sync.delete_catalog_video_live
    assert delete_route.dependant.call is sync.delete_catalog_video_live


def test_reordered_catalog_resolves_company_section_by_stable_identity():
    from app.models.remote_training_links import RemoteTrainingCatalogSectionLink
    from app.services import remote_training_live_video_sync as sync

    db = _db()
    package, catalog_a, catalog_b, program, section_a, section_b, *_ = _fixture_rows(db)
    _reorder_catalog_only(db, catalog_a, catalog_b)

    created = sync.ensure_catalog_section_links_for_package(db, package)
    db.flush()
    resolved = sync._program_section_for_catalog_section(db, program, package, catalog_b)

    assert created == 2
    assert resolved is not None
    assert resolved.id == section_b.id
    assert resolved.id != section_a.id
    link = db.scalar(
        select(RemoteTrainingCatalogSectionLink).where(
            RemoteTrainingCatalogSectionLink.program_id == program.id,
            RemoteTrainingCatalogSectionLink.catalog_section_id == catalog_b.id,
        )
    )
    assert link is not None
    assert link.program_section_id == section_b.id


def test_live_delete_after_reorder_never_archives_same_order_video_from_other_section(monkeypatch):
    from app.services import remote_training_live_video_sync as sync

    db = _db()
    package, catalog_a, catalog_b, program, section_a, section_b, catalog_video, video_a, video_b = _fixture_rows(db)
    sync.ensure_catalog_section_links_for_package(db, package)
    db.commit()
    _reorder_catalog_only(db, catalog_a, catalog_b)
    _patch_side_effects(monkeypatch, sync)

    changed = sync._deactivate_catalog_video_in_programs(
        db,
        user=SimpleNamespace(id=1),
        package=package,
        catalog_video=catalog_video,
    )
    db.flush()
    db.refresh(video_a)
    db.refresh(video_b)

    assert changed == 1
    assert video_b.status == "archived"
    assert video_b.is_current is False
    assert video_a.status == "published"
    assert video_a.is_current is True


def test_live_publish_after_reorder_replaces_only_the_linked_section(monkeypatch):
    from app.models.remote_training import RemoteTrainingVideo
    from app.services import remote_training_live_video_sync as sync

    db = _db()
    package, catalog_a, catalog_b, program, section_a, section_b, catalog_video, video_a, video_b = _fixture_rows(db)
    sync.ensure_catalog_section_links_for_package(db, package)
    db.commit()
    _reorder_catalog_only(db, catalog_a, catalog_b)
    _patch_side_effects(monkeypatch, sync)

    class _Store:
        def delete(self, _key):
            return None

    monkeypatch.setattr(sync.remote_api, "_remote_training_video_store", lambda: _Store())
    monkeypatch.setattr(sync, "_copy_storage_object", lambda *_a, **_k: None)
    monkeypatch.setattr(
        sync.remote_api,
        "storage_key",
        lambda **_k: "program/b-v2-copy.mp4",
    )

    synced, copied = sync._sync_published_catalog_video(
        db,
        user=SimpleNamespace(id=1),
        package=package,
        catalog_video=catalog_video,
    )
    db.flush()
    db.refresh(video_a)
    db.refresh(video_b)

    assert synced == 1
    assert copied == ["program/b-v2-copy.mp4"]
    assert video_a.is_current is True
    assert video_a.status == "published"
    assert video_b.is_current is False
    assert video_b.status == "unpublished"

    new_b = db.scalar(
        select(RemoteTrainingVideo).where(
            RemoteTrainingVideo.program_id == program.id,
            RemoteTrainingVideo.section_id == section_b.id,
            RemoteTrainingVideo.is_current.is_(True),
        )
    )
    assert new_b is not None
    assert new_b.original_file_name == "b-v2.mp4"
    assert new_b.storage_key == "program/b-v2-copy.mp4"