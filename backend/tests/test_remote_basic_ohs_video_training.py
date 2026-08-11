"""Regression tests for the isolated Basic OHS remote-training layer."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import pytest
from fastapi.testclient import TestClient


def _db():
    from app.core.database import Base
    from app.models import entities  # noqa: F401
    from app.models import remote_training  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


def _scope_rows(db: Session):
    from app.models.entities import Branch, Company, Employee, OsgbOrganization, User, UserRole

    osgb = OsgbOrganization(name="Remote Test OSGB", is_active=True)
    db.add(osgb)
    db.flush()
    company = Company(
        name="Remote Test Firma",
        osgb_id=osgb.id,
        sgk_registry_no="SGK-REMOTE-1",
        nace_code="46.83.06",
        hazard_class="Tehlikeli",
        is_active=True,
    )
    db.add(company)
    db.flush()
    branch = Branch(
        company_id=company.id,
        name="Merkez İşyeri",
        sgk_registry_no="SGK-BRANCH-1",
        is_active=True,
    )
    employee = Employee(company_id=company.id, branch=branch, full_name="Çalışan Test", is_active=True)
    user = User(
        email="employee-remote@test.invalid",
        full_name="Çalışan Kullanıcısı",
        hashed_password="x",
        role=UserRole.READ_ONLY,
        is_active=True,
    )
    db.add_all([branch, employee, user])
    db.flush()
    return osgb, company, branch, employee, user


def test_remote_video_validation_rejects_mismatched_content():
    from app.services.remote_training import validate_video_bytes

    valid_mp4_header = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
    validate_video_bytes(valid_mp4_header, extension=".mp4", original_name="ders.mp4")

    import pytest

    with pytest.raises(Exception):
        validate_video_bytes(b"not-a-video", extension=".mp4", original_name="ders.mp4")


def test_remote_assignment_recalculation_requires_real_progress_and_exam():
    from app.models.remote_training import (
        RemoteTrainingAssignment,
        RemoteTrainingProgram,
        RemoteTrainingSection,
        RemoteTrainingVideo,
        RemoteTrainingVideoProgress,
    )
    from app.services.remote_training import recalculate_assignment

    engine = _db()
    with Session(engine) as db:
        osgb, company, branch, employee, _user = _scope_rows(db)
        program = RemoteTrainingProgram(
            osgb_id=osgb.id,
            company_id=company.id,
            title="Basic Occupational Health and Safety Training",
            requires_final_exam=False,
            completion_threshold_percent=90,
        )
        db.add(program)
        db.flush()
        section = RemoteTrainingSection(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            title="Temel bölüm",
            is_required=True,
        )
        db.add(section)
        db.flush()
        video = RemoteTrainingVideo(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            section_id=section.id,
            title="Temel İSG video dersi",
            original_file_name="ders.mp4",
            content_type="video/mp4",
            storage_key="1/remote-basic-ohs/1/video-test.mp4",
            duration_seconds=100,
            status="published",
            is_current=True,
        )
        db.add(video)
        db.flush()
        assignment = RemoteTrainingAssignment(
            osgb_id=osgb.id,
            company_id=company.id,
            branch_id=branch.id,
            program_id=program.id,
            employee_id=employee.id,
            employee_name_snapshot=employee.full_name,
            workplace_name_snapshot=branch.name,
            sgk_registration_number_snapshot=branch.sgk_registry_no,
            nace_code_snapshot=company.nace_code,
            nace_description_snapshot="Metalden prefabrik yapıların toptan ticareti",
            hazard_class_snapshot=company.hazard_class,
        )
        db.add(assignment)
        db.flush()

        first = recalculate_assignment(db, assignment)
        assert first["complete"] is False
        assert assignment.status == "not_started"

        db.add(
            RemoteTrainingVideoProgress(
                company_id=company.id,
                program_id=program.id,
                assignment_id=assignment.id,
                section_id=section.id,
                video_id=video.id,
                employee_id=employee.id,
                last_position_seconds=91,
                watched_duration_seconds=91,
                watched_percentage=91,
                status="completed",
                completed_at=datetime.utcnow(),
            )
        )
        db.flush()
        second = recalculate_assignment(db, assignment)
        assert second["complete"] is True
        assert assignment.status == "completed"


def test_mapped_employee_access_does_not_need_legacy_user_employee_id():
    from app.models.remote_training import RemoteTrainingAssignment, RemoteTrainingEmployeeAccess
    from app.services.remote_training import assert_assignment_access

    engine = _db()
    with Session(engine) as db:
        osgb, company, branch, employee, user = _scope_rows(db)
        assignment = RemoteTrainingAssignment(
            osgb_id=osgb.id,
            company_id=company.id,
            branch_id=branch.id,
            program_id=1,
            employee_id=employee.id,
            employee_name_snapshot=employee.full_name,
        )
        db.add(assignment)
        db.flush()
        db.add(
            RemoteTrainingEmployeeAccess(
                osgb_id=osgb.id,
                company_id=company.id,
                user_id=user.id,
                employee_id=employee.id,
                is_active=True,
            )
        )
        db.flush()
        assert assert_assignment_access(db, user, assignment) == "employee"


@pytest.fixture()
def remote_client(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'remote-api.db').as_posix()}"
    from app.core.config import settings

    monkeypatch.setattr(settings, "database_url", url)
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "remote_basic_ohs_training_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_training_force_off", False)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    import app.core.database as dbmod
    import app.main as main_mod

    engine = create_engine(url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(dbmod, "engine", engine)
    session_factory = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    monkeypatch.setattr(dbmod, "SessionLocal", session_factory)
    monkeypatch.setattr(main_mod, "engine", engine)
    monkeypatch.setattr(main_mod, "SessionLocal", session_factory)
    from app.core.database import Base

    Base.metadata.create_all(bind=engine)
    yield TestClient(main_mod.app)


def test_remote_api_is_feature_flagged_and_uses_basic_type_only(remote_client):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="API Remote OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="API Remote Firma", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        db.add(
            User(
                email="remote-admin@remote-test.com",
                full_name="Remote Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                company_id=company.id,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()
        company_id = company.id

    login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "remote-admin@remote-test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    meta = remote_client.get("/api/v1/trainings/remote/meta", headers=headers)
    assert meta.status_code == 200, meta.text
    assert meta.json()["enabled"] is True
    assert meta.json()["training_type"] == "Basic Occupational Health and Safety Training"

    created = remote_client.post(
        "/api/v1/trainings/remote/programs",
        headers=headers,
        json={"company_id": company_id, "title": "Basic Occupational Health and Safety Training"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["training_type"] == "Basic Occupational Health and Safety Training"

    from app.core.config import settings

    settings.remote_basic_ohs_training_force_off = True
    blocked = remote_client.get("/api/v1/trainings/remote/programs", headers=headers)
    assert blocked.status_code == 404
    settings.remote_basic_ohs_training_force_off = False


def test_remote_video_delete_removes_only_draft_uploads(remote_client, monkeypatch):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, OsgbOrganization, User, UserRole
    from app.models.remote_training import (
        RemoteTrainingProgram,
        RemoteTrainingSection,
        RemoteTrainingVideo,
    )

    class FakeStore:
        def __init__(self):
            self.deleted = []

        def delete(self, key):
            self.deleted.append(key)

    store = FakeStore()
    import app.api.remote_training as remote_api

    monkeypatch.setattr(remote_api, "get_object_store", lambda: store)

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Delete Test OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Delete Test Firma", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        db.add(
            User(
                email="delete-admin@remote-test.com",
                full_name="Delete Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                company_id=company.id,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        program = RemoteTrainingProgram(
            osgb_id=osgb.id,
            company_id=company.id,
            title="Basic Occupational Health and Safety Training",
            status="draft",
        )
        db.add(program)
        db.flush()
        section = RemoteTrainingSection(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            title="Temel bölüm",
        )
        db.add(section)
        db.flush()
        draft = RemoteTrainingVideo(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            section_id=section.id,
            title="Yanlış yüklenen video",
            original_file_name="yanlis.mp4",
            content_type="video/mp4",
            storage_key="1/remote-basic-ohs/1/video-delete.mp4",
            duration_seconds=123,
            status="uploading",
        )
        published = RemoteTrainingVideo(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            section_id=section.id,
            title="Yayımlanmış video",
            original_file_name="yayinda.mp4",
            content_type="video/mp4",
            storage_key="1/remote-basic-ohs/1/video-published.mp4",
            duration_seconds=456,
            status="published",
        )
        db.add_all([draft, published])
        db.commit()
        draft_id = draft.id
        published_id = published.id
        program_id = program.id

    login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "delete-admin@remote-test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    deleted = remote_client.delete(f"/api/v1/trainings/remote/videos/{draft_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {
        "deleted": True,
        "id": draft_id,
        "storage_cleanup_pending": False,
    }
    assert store.deleted == ["1/remote-basic-ohs/1/video-delete.mp4"]

    with SessionLocal() as db:
        assert db.get(RemoteTrainingVideo, draft_id) is None
        retained = db.get(RemoteTrainingVideo, published_id)
        assert retained is not None
        assert retained.status == "published"
        program_row = db.get(RemoteTrainingProgram, program_id)
        assert program_row is not None
        assert program_row.total_duration_seconds == 456

    blocked = remote_client.delete(f"/api/v1/trainings/remote/videos/{published_id}", headers=headers)
    assert blocked.status_code == 409, blocked.text
    assert store.deleted == ["1/remote-basic-ohs/1/video-delete.mp4"]
