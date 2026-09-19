from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def _db() -> Session:
    from app.core.database import Base
    from app.models import entities  # noqa: F401
    from app.models import remote_training  # noqa: F401
    from app.models import remote_training_links  # noqa: F401
    from app.models import training_presentation  # noqa: F401
    from app.models import training_presentation_approval  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _workplace_user(company_id: int = 42, *, email: str = "isyeri@example.test"):
    from app.models.entities import UserRole

    return SimpleNamespace(
        id=7,
        role=UserRole.COMPANY_ADMIN,
        company_id=company_id,
        osgb_id=3,
        email=email,
        full_name="İşyeri Yetkilisi",
    )


def test_generated_workplace_password_account_is_assignment_operator_only():
    from app.api import remote_training as remote_api
    from app.services.remote_training import is_manager, is_workplace_account

    user = _workplace_user(email="isyeri.42@kiosk.isgsuite.tr")
    assert is_manager(user) is True
    assert is_workplace_account(user) is True

    with pytest.raises(HTTPException) as catalog_error:
        remote_api._assert_catalog_reader(user)
    assert catalog_error.value.status_code == 403

    with pytest.raises(HTTPException) as distribution_error:
        remote_api._assert_catalog_distribution_manager(user)
    assert distribution_error.value.status_code == 403


def test_workplace_account_cannot_read_or_distribute_catalog_packages():
    from app.api import remote_training as remote_api

    user = _workplace_user()
    with pytest.raises(HTTPException) as reader_error:
        remote_api._assert_catalog_reader(user)
    assert reader_error.value.status_code == 403

    with pytest.raises(HTTPException) as distributor_error:
        remote_api._assert_catalog_distribution_manager(user)
    assert distributor_error.value.status_code == 403


def test_workplace_program_list_contains_catalog_and_grandfathered_rows(monkeypatch):
    from app.api import remote_training as remote_api
    from app.models.remote_training import RemoteTrainingProgram

    db = _db()
    db.add_all(
        [
            RemoteTrainingProgram(
                osgb_id=3,
                company_id=42,
                title="Eski manuel program",
                source_catalog_package_id=None,
                status="published",
            ),
            RemoteTrainingProgram(
                osgb_id=3,
                company_id=42,
                title="Yeni manuel program",
                source_catalog_package_id=None,
                created_by_id=88,
                workplace_assignment_allowed=False,
            ),
            RemoteTrainingProgram(
                osgb_id=3,
                company_id=42,
                title="Uzman tarafından tanımlanan paket",
                source_catalog_package_id=9,
                source_catalog_code="common-basic-ohs",
                status="published",
            ),
            RemoteTrainingProgram(
                osgb_id=4,
                company_id=99,
                title="Başka işyeri paketi",
                source_catalog_package_id=10,
                source_catalog_code="office-general-ohs",
                status="published",
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(remote_api, "require_feature", lambda: None)

    rows = remote_api.list_remote_programs(
        company_id=None,
        status=None,
        db=db,
        user=_workplace_user(),
    )

    assert {row["title"] for row in rows} == {
        "Eski manuel program",
        "Uzman tarafından tanımlanan paket",
    }
    assert "Yeni manuel program" not in {row["title"] for row in rows}
    assert all(row["company_id"] == 42 for row in rows)


def test_workplace_cannot_open_new_manual_program_by_id():
    from app.api import remote_training as remote_api
    from app.models.remote_training import RemoteTrainingProgram

    db = _db()
    row = RemoteTrainingProgram(
        osgb_id=3,
        company_id=42,
        title="Eski manuel program",
        source_catalog_package_id=None,
        created_by_id=99,
        workplace_assignment_allowed=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    with pytest.raises(HTTPException) as error:
        remote_api._assert_program_manager(db, _workplace_user(), row.id)
    assert error.value.status_code == 404
