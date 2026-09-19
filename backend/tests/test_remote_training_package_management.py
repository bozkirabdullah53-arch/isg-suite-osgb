from __future__ import annotations

import pytest

from types import SimpleNamespace

from sqlalchemy import create_engine
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


def _package(db: Session, *, title: str = "Deneme Paketi"):
    from app.models.remote_training import RemoteTrainingCatalogPackage

    row = RemoteTrainingCatalogPackage(
        osgb_id=77,
        code="common-basic-ohs",
        title=title,
        status="draft",
        revision_no=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_package_metadata_update_changes_only_catalog_record(monkeypatch):
    from app.services import remote_training_package_management as management

    db = _db()
    package = _package(db)
    monkeypatch.setattr(
        management,
        "_private_package",
        lambda session, _user, package_id: session.get(type(package), package_id),
    )

    out = management.update_catalog_package_metadata(
        package.id,
        management.RemoteCatalogPackageMetadataUpdate(
            title="  Yeni   Paket   Adı  ",
            description="Yeni açıklama",
        ),
        db=db,
        user=SimpleNamespace(id=1),
    )

    db.refresh(package)
    assert package.title == "Yeni Paket Adı"
    assert package.description == "Yeni açıklama"
    assert package.revision_no == 2
    assert out["title"] == "Yeni Paket Adı"


def test_archived_catalog_package_metadata_requires_restore(monkeypatch):
    from fastapi import HTTPException

    from app.services import remote_training_package_management as management

    db = _db()
    package = _package(db)
    package.status = "archived"
    db.commit()
    monkeypatch.setattr(
        management,
        "_private_package",
        lambda session, _user, package_id: session.get(type(package), package_id),
    )

    with pytest.raises(HTTPException) as exc_info:
        management.update_catalog_package_metadata(
            package.id,
            management.RemoteCatalogPackageMetadataUpdate(title="Yeni Paket Adı"),
            db=db,
            user=SimpleNamespace(id=1),
        )

    assert exc_info.value.status_code == 409
    assert "düzenlemeye açın" in str(exc_info.value.detail)
    db.refresh(package)
    assert package.title == "Deneme Paketi"
    assert package.revision_no == 1


def test_used_catalog_package_can_be_deleted_without_historical_program(monkeypatch):
    from app.models.remote_training import RemoteTrainingProgram
    from app.services import remote_training_package_management as management

    db = _db()
    package = _package(db)
    program = RemoteTrainingProgram(
        osgb_id=77,
        company_id=909,
        source_catalog_package_id=package.id,
        source_catalog_code=package.code,
        source_catalog_revision_no=package.revision_no,
        title=package.title,
        status="published",
    )
    db.add(program)
    db.commit()
    monkeypatch.setattr(
        management,
        "_private_package",
        lambda session, _user, package_id: session.get(type(package), package_id),
    )

    out = management.delete_catalog_package_safely(
        package.id,
        db=db,
        user=SimpleNamespace(id=1),
    )

    assert out["deleted"] is True
    assert out["history_preserved"] is True
    assert out["materialized_program_count"] == 1
    assert db.get(type(package), package.id) is None
    db.refresh(program)
    assert program.source_catalog_package_id is None
    assert program.source_catalog_code == package.code
    assert db.get(RemoteTrainingProgram, program.id) is not None


def test_unused_catalog_package_can_be_deleted(monkeypatch):
    from app.services import remote_training_package_management as management

    db = _db()
    package = _package(db, title="Yanlış Eklenen Paket")
    package_id = package.id
    monkeypatch.setattr(
        management,
        "_private_package",
        lambda session, _user, wanted_id: session.get(type(package), wanted_id),
    )

    out = management.delete_catalog_package_safely(
        package_id,
        db=db,
        user=SimpleNamespace(id=1),
    )
    assert out["deleted"] is True
    assert out["history_preserved"] is False
    assert out["materialized_program_count"] == 0
    assert db.get(type(package), package_id) is None


def test_management_route_installer_is_idempotent():
    from app.api import remote_training as remote_api
    from app.services import remote_training_package_management as management

    first = management.install_remote_training_package_management()
    second = management.install_remote_training_package_management()
    assert first["installed"] is True
    assert second["installed"] is True
    assert second["already_installed"] is True

    routes = {
        (str(getattr(route, "path", "")), method)
        for route in remote_api.router.routes
        for method in (getattr(route, "methods", set()) or set())
    }
    assert ("/trainings/remote/catalog/packages/{package_id}", "PATCH") in routes
    assert ("/trainings/remote/catalog/packages/{package_id}", "DELETE") in routes
    assert ("/trainings/remote/catalog/sections/{section_id}", "PATCH") in routes
    assert ("/trainings/remote/catalog/sections/{section_id}", "DELETE") in routes
    assert ("/trainings/remote/catalog/packages/{package_id}/sections/order", "PATCH") in routes


def test_company_assignment_update_and_remove_preserve_central_catalog(monkeypatch):
    from app.api import remote_training as remote_api
    from app.models.remote_training import RemoteTrainingProgram

    db = _db()
    package = _package(db, title="Merkezi Paket")
    program = RemoteTrainingProgram(
        osgb_id=77,
        company_id=909,
        source_catalog_package_id=package.id,
        source_catalog_code=package.code,
        source_catalog_revision_no=package.revision_no,
        title=package.title,
        status="published",
    )
    db.add(program)
    db.commit()
    db.refresh(program)
    user = SimpleNamespace(id=12)

    monkeypatch.setattr(remote_api, "_assert_program_assignment_manager", lambda _db, _user, _id: program)
    updated = remote_api.update_remote_program_assignment(
        program.id,
        remote_api.RemoteProgramAssignmentUpdate(
            title="Firma için güncellenmiş paket",
            description="Firma açıklaması",
        ),
        db=db,
        user=user,
    )
    assert updated["title"] == "Firma için güncellenmiş paket"
    assert updated["description"] == "Firma açıklaması"

    removed = remote_api._remove_company_program(db, user, program)
    db.commit()
    assert removed["removed"] is True
    assert removed["history_preserved"] is True
    db.refresh(program)
    assert program.status == "archived"
    assert db.get(type(package), package.id) is not None
    assert db.get(RemoteTrainingProgram, program.id) is not None


def test_company_assignment_management_routes_are_registered():
    from app.api import remote_training as remote_api

    routes = {
        (str(getattr(route, "path", "")), method)
        for route in remote_api.router.routes
        for method in (getattr(route, "methods", set()) or set())
    }
    assert ("/trainings/remote/programs/{program_id}/assignment", "PATCH") in routes
    assert ("/trainings/remote/programs/{program_id}", "DELETE") in routes
    assert ("/trainings/remote/programs", "DELETE") in routes


def test_catalog_section_reorder_uses_contiguous_order_and_preserves_snapshot_boundary(monkeypatch):
    from sqlalchemy import select

    from app.models.remote_training import RemoteTrainingCatalogSection
    from app.services import remote_training_package_management as management

    db = _db()
    package = _package(db)
    sections = [
        RemoteTrainingCatalogSection(
            package_id=package.id,
            code=f"SEC-{index}",
            title=f"Bölüm {index}",
            order_index=index,
        )
        for index in (1, 2, 3)
    ]
    db.add_all(sections)
    db.commit()
    for section in sections:
        db.refresh(section)

    monkeypatch.setattr(
        management,
        "_private_package",
        lambda session, _user, package_id: session.get(type(package), package_id),
    )
    out = management.reorder_catalog_sections(
        package.id,
        management.RemoteCatalogSectionReorder(
            section_ids=[sections[2].id, sections[0].id, sections[1].id],
        ),
        db=db,
        user=SimpleNamespace(id=1),
    )

    rows = list(
        db.scalars(
            select(RemoteTrainingCatalogSection)
            .where(RemoteTrainingCatalogSection.package_id == package.id)
            .order_by(RemoteTrainingCatalogSection.order_index)
        ).all()
    )
    assert [row.id for row in rows] == [sections[2].id, sections[0].id, sections[1].id]
    assert [row.order_index for row in rows] == [1, 2, 3]
    db.refresh(package)
    assert package.revision_no == 2
    assert out["reordered"] is True
