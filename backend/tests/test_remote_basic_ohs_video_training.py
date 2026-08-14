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
        email="employee-remote@example.com",
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


def test_strict_remote_policy_rollout_is_fail_closed(monkeypatch):
    from app.core.config import remote_basic_ohs_strict_policy_active, settings

    monkeypatch.setattr(settings, "remote_basic_ohs_training_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_force_off", False)
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_package_codes", "working-at-height-ohs")
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_pilot_company_ids", "42")
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_enabled", False)
    assert not remote_basic_ohs_strict_policy_active("working-at-height-ohs", 42)

    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_enabled", True)
    assert not remote_basic_ohs_strict_policy_active("working-at-height-ohs", 41)
    assert remote_basic_ohs_strict_policy_active("working-at-height-ohs", 42)
    assert not remote_basic_ohs_strict_policy_active("construction-ohs", 42)

    # Manual firm/sector assignment: an empty company allowlist does not
    # auto-assign anything; it lets the manager choose the target firm.
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_package_codes", "construction-ohs")
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_pilot_company_ids", "")
    assert remote_basic_ohs_strict_policy_active("construction-ohs", 999)

    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_force_off", True)
    assert not remote_basic_ohs_strict_policy_active("working-at-height-ohs", 42)


def test_catalog_package_sections_keep_their_sector_identity():
    from app.models.remote_training import catalog_package_sector_code

    expected = {
        "common-basic-ohs": "common",
        "construction-ohs": "construction",
        "metal-machine-ohs": "metal",
        "battery-production-ohs": "battery",
        "food-production-ohs": "food",
        "logistics-warehouse-transport-ohs": "logistics",
        "chemical-paint-production-ohs": "chemical",
        "open-mine-quarry-aggregate-ohs": "mining",
        "road-asphalt-infrastructure-ohs": "road",
        "office-general-ohs": "office",
        "working-at-height-ohs": "working_at_height",
    }
    assert {code: catalog_package_sector_code(code) for code in expected} == expected
    # Custom/future packages remain backward compatible until explicitly mapped.
    assert catalog_package_sector_code("future-custom-package") == "common"


def test_catalog_packages_receive_ten_relevant_automatic_exam_questions():
    from app.services.remote_training import automatic_exam_items_for_package

    package_codes = (
        "common-basic-ohs",
        "construction-ohs",
        "metal-machine-ohs",
        "battery-production-ohs",
        "food-production-ohs",
        "logistics-warehouse-transport-ohs",
        "chemical-paint-production-ohs",
        "open-mine-quarry-aggregate-ohs",
        "road-asphalt-infrastructure-ohs",
        "office-general-ohs",
        "working-at-height-ohs",
    )
    for package_code in package_codes:
        items = automatic_exam_items_for_package(package_code)
        assert len(items) == 10
        assert len({item["question_code"] for item in items}) == 10
        assert len({item["topic_code"] for item in items}) == 10
        assert all(
            item["question_text"]
            and len(item["options"]) == 4
            and item["correct_option"] in "ABCD"
            and item["answer_explanation"]
            and item["sources"]
            for item in items
        )

    height_items = automatic_exam_items_for_package("working-at-height-ohs")
    assert len({item["topic_code"] for item in height_items}) == 10

    with pytest.raises(RuntimeError):
        automatic_exam_items_for_package("future-custom-package")


def test_strict_video_coverage_does_not_double_count_replay():
    from app.services.remote_training import _merge_coverage

    coverage, total = _merge_coverage([], 0, 10, 100)
    assert coverage == [[0.0, 10.0]]
    assert total == 10.0

    replayed, replayed_total = _merge_coverage(coverage, 0, 10, 100)
    assert replayed == coverage
    assert replayed_total == 10.0

    extended, extended_total = _merge_coverage(replayed, 10, 20, 100)
    assert extended == [[0.0, 20.0]]
    assert extended_total == 20.0


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


def test_strict_remote_exam_requires_seventy_percent_for_completion():
    from app.models.remote_training import (
        RemoteTrainingAssignment,
        RemoteTrainingExamAttempt,
        RemoteTrainingProgram,
        RemoteTrainingQuestion,
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
            title="Yüksekte Çalışma",
            completion_threshold_percent=100,
            passing_score=70,
            requires_final_exam=True,
            policy_mode="strict",
            sequence_enforced=True,
            exam_gate_enforced=True,
        )
        db.add(program)
        db.flush()
        section = RemoteTrainingSection(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            sector_code="working_at_height",
            title="Yüksekte çalışma",
        )
        db.add(section)
        db.flush()
        video = RemoteTrainingVideo(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            section_id=section.id,
            title="Yüksekte çalışma videosu",
            original_file_name="yuksekte.mp4",
            content_type="video/mp4",
            storage_key="1/remote-basic-ohs/yuksekte.mp4",
            duration_seconds=100,
            status="published",
            is_current=True,
        )
        db.add(video)
        db.flush()
        for position in range(1, 11):
            db.add(
                RemoteTrainingQuestion(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    program_id=program.id,
                    sector_code="working_at_height",
                    question_text=f"Yüksekte çalışma sorusu {position}",
                    options_json='{"A":"Doğru","B":"Yanlış","C":"Diğer","D":"Belirsiz"}',
                    correct_option="A",
                    is_final_exam=True,
                    order_index=position,
                )
            )
        assignment = RemoteTrainingAssignment(
            osgb_id=osgb.id,
            company_id=company.id,
            branch_id=branch.id,
            program_id=program.id,
            employee_id=employee.id,
            employee_name_snapshot=employee.full_name,
        )
        db.add(assignment)
        db.flush()
        db.add(
            RemoteTrainingVideoProgress(
                company_id=company.id,
                program_id=program.id,
                assignment_id=assignment.id,
                section_id=section.id,
                video_id=video.id,
                employee_id=employee.id,
                last_position_seconds=100,
                watched_duration_seconds=100,
                watched_percentage=100,
                status="completed",
                completed_at=datetime.utcnow(),
            )
        )
        db.flush()
        db.add(
            RemoteTrainingExamAttempt(
                company_id=company.id,
                program_id=program.id,
                assignment_id=assignment.id,
                employee_id=employee.id,
                attempt_no=1,
                question_ids_json="[1,2,3,4,5,6,7,8,9,10]",
                answers_json="{}",
                score=69,
                passed=False,
            )
        )
        db.flush()
        failed = recalculate_assignment(db, assignment)
        assert failed["exam_passed"] is False
        assert failed["complete"] is False

        db.add(
            RemoteTrainingExamAttempt(
                company_id=company.id,
                program_id=program.id,
                assignment_id=assignment.id,
                employee_id=employee.id,
                attempt_no=2,
                question_ids_json="[1,2,3,4,5,6,7,8,9,10]",
                answers_json="{}",
                score=70,
                passed=True,
            )
        )
        db.flush()
        passed = recalculate_assignment(db, assignment)
        assert passed["exam_passed"] is True
        assert passed["complete"] is True


def test_remote_assignment_sector_snapshot_limits_required_content():
    from app.models.remote_training import (
        RemoteTrainingAssignment,
        RemoteTrainingAssignmentSector,
        RemoteTrainingProgram,
        RemoteTrainingProgramQuestion,
        RemoteTrainingProgramSector,
        RemoteTrainingQuestion,
        RemoteTrainingSection,
        RemoteTrainingVideo,
    )
    from app.api.remote_training import _exam_links_for_assignment, _program_detail
    from app.models.entities import TrainingQuestion
    from app.services.remote_training import recalculate_assignment

    engine = _db()
    with Session(engine) as db:
        osgb, company, branch, employee, _user = _scope_rows(db)
        program = RemoteTrainingProgram(
            osgb_id=osgb.id,
            company_id=company.id,
            title="Basic Occupational Health and Safety Training",
            requires_final_exam=False,
        )
        db.add(program)
        db.flush()
        db.add_all(
            [
                RemoteTrainingProgramSector(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    program_id=program.id,
                    sector_code="common",
                    sector_name_snapshot="Temel Ortak İSG",
                    is_enabled=True,
                ),
                RemoteTrainingProgramSector(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    program_id=program.id,
                    sector_code="construction",
                    sector_name_snapshot="İnşaat",
                    is_enabled=True,
                ),
            ]
        )
        common_section = RemoteTrainingSection(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            sector_code="common",
            title="Ortak bölüm",
        )
        construction_section = RemoteTrainingSection(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            sector_code="construction",
            title="İnşaat bölümü",
            order_index=2,
        )
        db.add_all([common_section, construction_section])
        db.flush()
        common_video = RemoteTrainingVideo(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            section_id=common_section.id,
            title="Ortak video",
            original_file_name="ortak.mp4",
            content_type="video/mp4",
            storage_key="1/remote-basic-ohs/common.mp4",
            duration_seconds=100,
            status="published",
            is_current=True,
        )
        construction_video = RemoteTrainingVideo(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            section_id=construction_section.id,
            title="İnşaat video",
            original_file_name="insaat.mp4",
            content_type="video/mp4",
            storage_key="1/remote-basic-ohs/construction.mp4",
            duration_seconds=100,
            status="published",
            is_current=True,
        )
        db.add_all([common_video, construction_video])
        db.flush()
        db.add_all(
            [
                RemoteTrainingQuestion(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    program_id=program.id,
                    sector_code="common",
                    question_text="Ortak soru",
                    options_json='{"A":"1","B":"2","C":"3","D":"4"}',
                    correct_option="A",
                    is_required=True,
                ),
                RemoteTrainingQuestion(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    program_id=program.id,
                    sector_code="construction",
                    question_text="İnşaat sorusu",
                    options_json='{"A":"1","B":"2","C":"3","D":"4"}',
                    correct_option="A",
                    is_required=True,
                ),
            ]
        )
        db.flush()
        bank_common = TrainingQuestion(
            question_code="REMOTE-COMMON-1",
            version=1,
            status="published",
            topic_code="remote-common",
            topic_label="Temel Ortak İSG",
            question_text="Ortak final sorusu",
            option_a="1",
            option_b="2",
            option_c="3",
            option_d="4",
            correct_option="A",
            answer_explanation="",
            created_by_id=_user.id,
        )
        bank_construction = TrainingQuestion(
            question_code="REMOTE-CONSTRUCTION-1",
            version=1,
            status="published",
            topic_code="remote-construction",
            topic_label="İnşaat",
            question_text="İnşaat final sorusu",
            option_a="1",
            option_b="2",
            option_c="3",
            option_d="4",
            correct_option="A",
            answer_explanation="",
            created_by_id=_user.id,
        )
        db.add_all([bank_common, bank_construction])
        db.flush()
        db.add_all(
            [
                RemoteTrainingProgramQuestion(
                    company_id=company.id,
                    program_id=program.id,
                    question_id=bank_common.id,
                    sector_code="common",
                    position=1,
                ),
                RemoteTrainingProgramQuestion(
                    company_id=company.id,
                    program_id=program.id,
                    question_id=bank_construction.id,
                    sector_code="construction",
                    position=2,
                ),
            ]
        )
        assignment = RemoteTrainingAssignment(
            osgb_id=osgb.id,
            company_id=company.id,
            branch_id=branch.id,
            program_id=program.id,
            employee_id=employee.id,
            employee_name_snapshot=employee.full_name,
        )
        db.add(assignment)
        db.flush()
        db.add(
            RemoteTrainingAssignmentSector(
                osgb_id=osgb.id,
                company_id=company.id,
                program_id=program.id,
                assignment_id=assignment.id,
                employee_id=employee.id,
                sector_code="common",
                sector_name_snapshot="Temel Ortak İSG",
            )
        )
        db.flush()

        common_only = recalculate_assignment(db, assignment)
        assert common_only["sector_codes"] == ["common"]
        assert common_only["required_video_count"] == 1
        assert common_only["required_checkpoint_count"] == 1
        assert [link.sector_code for link in _exam_links_for_assignment(db, assignment)] == ["common"]

        program.status = "published"
        employee_view = _program_detail(db, program, employee=True, sector_codes={"common"})
        assert [section["sector_code"] for section in employee_view["sections"]] == ["common"]
        assert [question["sector_code"] for question in employee_view["checkpoint_questions"]] == ["common"]

        db.add(
            RemoteTrainingAssignmentSector(
                osgb_id=osgb.id,
                company_id=company.id,
                program_id=program.id,
                assignment_id=assignment.id,
                employee_id=employee.id,
                sector_code="construction",
                sector_name_snapshot="İnşaat",
            )
        )
        db.flush()
        expanded = recalculate_assignment(db, assignment)
        assert expanded["sector_codes"] == ["common", "construction"]
        assert expanded["required_video_count"] == 2
        assert expanded["required_checkpoint_count"] == 2
        assert [link.sector_code for link in _exam_links_for_assignment(db, assignment)] == ["common", "construction"]


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

    program_id = created.json()["id"]
    scope = remote_client.get(f"/api/v1/trainings/remote/programs/{program_id}/sectors", headers=headers)
    assert scope.status_code == 200, scope.text
    assert scope.json()["mode"] == "scoped"
    assert "common" in scope.json()["selected_sector_codes"]
    assert any(row["code"] == "construction" and not row["enabled"] for row in scope.json()["sectors"])

    updated_scope = remote_client.put(
        f"/api/v1/trainings/remote/programs/{program_id}/sectors",
        headers=headers,
        json={"sector_codes": ["construction"]},
    )
    assert updated_scope.status_code == 200, updated_scope.text
    assert updated_scope.json()["selected_sector_codes"] == ["construction"]

    from app.core.config import settings

    settings.remote_basic_ohs_training_force_off = True
    blocked = remote_client.get("/api/v1/trainings/remote/programs", headers=headers)
    assert blocked.status_code == 404
    settings.remote_basic_ohs_training_force_off = False


def test_remote_catalog_packages_are_firm_independent(remote_client, monkeypatch):
    """The new catalog is seeded without a company and stays assignable later."""
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, OsgbOrganization, User, UserRole
    from app.models.remote_training import (
        RemoteTrainingCatalogPackage,
        RemoteTrainingCatalogSection,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Catalog Test OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Catalog Test Firma", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        db.add(
            User(
                email="catalog-admin@remote-test.com",
                full_name="Catalog Admin",
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
        json={"email": "catalog-admin@remote-test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    packages = remote_client.get("/api/v1/trainings/remote/catalog/packages", headers=headers)
    assert packages.status_code == 200, packages.text
    rows = packages.json()
    assert len(rows) == 11
    assert [row["title"] for row in rows] == [
        "Ortak Temel İSG",
        "İnşaat",
        "Metal-Makine",
        "Akü-Batarya",
        "Gıda",
        "Lojistik",
        "Kimyasal/Boya",
        "Maden/Agrega",
        "Yol/Asfalt/Altyapı",
        "Ofis/Genel İşyerleri",
        "Yüksekte Çalışma İSG Paketi",
    ]
    assert all("company_id" not in row for row in rows)
    assert next(row for row in rows if row["code"] == "construction-ohs")["section_count"] == 12
    assert next(row for row in rows if row["code"] == "metal-machine-ohs")["section_count"] == 10
    assert next(row for row in rows if row["code"] == "battery-production-ohs")["section_count"] == 10
    assert next(row for row in rows if row["code"] == "working-at-height-ohs")["section_count"] == 10

    empty_package = next(row for row in rows if row["code"] == "food-production-ohs")
    created = remote_client.post(
        f"/api/v1/trainings/remote/catalog/packages/{empty_package['id']}/sections",
        headers=headers,
        json={"code": "GID-01", "title": "Gıda tesisi genel güvenlik"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["package_id"] == empty_package["id"]

    with SessionLocal() as db:
        package = db.get(RemoteTrainingCatalogPackage, empty_package["id"])
        assert package is not None
        assert not hasattr(package, "company_id")
        section = db.get(RemoteTrainingCatalogSection, created.json()["id"])
        assert section.package_id == package.id
        package.status = "published"
        db.commit()

    monkeypatch.setattr("app.core.config.settings.remote_basic_ohs_strict_policy_enabled", False)
    blocked_materialization = remote_client.post(
        f"/api/v1/trainings/remote/catalog/packages/{empty_package['id']}/materialize",
        headers=headers,
        json={"company_id": company_id},
    )
    assert blocked_materialization.status_code == 409, blocked_materialization.text
    assert "firma bazlı dağıtım" in blocked_materialization.json()["detail"]


def test_remote_catalog_video_upload_and_draft_delete(remote_client, monkeypatch):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, OsgbOrganization, User, UserRole

    class FakeStore:
        def __init__(self):
            self.puts = []
            self.deleted = []

        def put_bytes(self, key, content):
            self.puts.append((key, content))
            return key

        def delete(self, key):
            self.deleted.append(key)

    store = FakeStore()
    import app.api.remote_training as remote_api

    monkeypatch.setattr(remote_api, "get_object_store", lambda: store)
    monkeypatch.setattr("app.services.object_store.get_object_store", lambda: store)
    monkeypatch.setattr(remote_api, "enqueue_catalog_video_processing", lambda _db, _video: "job-catalog")

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Catalog Upload OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Catalog Upload Firma", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        db.add(
            User(
                email="catalog-upload-admin@remote-test.com",
                full_name="Catalog Upload Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                company_id=company.id,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()

    login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "catalog-upload-admin@remote-test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    packages = remote_client.get("/api/v1/trainings/remote/catalog/packages", headers=headers).json()
    package = next(row for row in packages if row["code"] == "battery-production-ohs")
    detail = remote_client.get(f"/api/v1/trainings/remote/catalog/packages/{package['id']}", headers=headers).json()
    section_id = next(row["id"] for row in detail["sections"] if row["code"] == "AKÜ-05")
    valid_mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16

    uploaded = remote_client.post(
        f"/api/v1/trainings/remote/catalog/sections/{section_id}/videos",
        headers=headers,
        data={"title": "AKÜ-05 test videosu"},
        files={"file": ("aku-05.mp4", valid_mp4, "video/mp4")},
    )
    assert uploaded.status_code == 201, uploaded.text
    row = uploaded.json()
    assert row["status"] == "uploading"
    assert row["package_id"] == package["id"]
    assert store.puts and store.puts[0][0].startswith("remote-basic-ohs/catalog/")

    deleted = remote_client.delete(f"/api/v1/trainings/remote/catalog/videos/{row['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert store.deleted == [store.puts[0][0]]


def test_remote_employee_account_onboarding_mapping(remote_client):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import User, UserRole

    with SessionLocal() as db:
        osgb, company, _branch, employee, employee_user = _scope_rows(db)
        employee_user.hashed_password = get_password_hash("TestPass123!")
        admin = User(
            email="employee-access-admin@remote-test.com",
            full_name="Employee Access Admin",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            company_id=company.id,
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        company_id = company.id
        employee_id = employee.id
        employee_user_id = employee_user.id

    login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "employee-access-admin@remote-test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    candidates = remote_client.get(
        f"/api/v1/trainings/remote/employee-access/candidates?company_id={company_id}",
        headers=admin_headers,
    )
    assert candidates.status_code == 200, candidates.text
    assert employee_id in {row["id"] for row in candidates.json()["employees"]}
    assert employee_user_id in {row["id"] for row in candidates.json()["users"]}

    mapped = remote_client.post(
        "/api/v1/trainings/remote/employee-access",
        headers=admin_headers,
        json={"company_id": company_id, "employee_id": employee_id, "user_id": employee_user_id},
    )
    assert mapped.status_code == 201, mapped.text

    employee_login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "employee-remote@example.com", "password": "TestPass123!"},
    )
    assert employee_login.status_code == 200, employee_login.text
    employee_headers = {"Authorization": f"Bearer {employee_login.json()['access_token']}"}
    meta = remote_client.get("/api/v1/trainings/remote/meta", headers=employee_headers)
    assert meta.status_code == 200, meta.text
    assert meta.json()["can_view_employee_panel"] is True
    assert remote_client.get("/api/v1/trainings/remote/my-assignments", headers=employee_headers).json() == []


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


def test_remote_published_video_can_be_revised_without_losing_history(remote_client, monkeypatch):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, OsgbOrganization, User, UserRole
    from app.models.remote_training import RemoteTrainingProgram, RemoteTrainingSection, RemoteTrainingVideo

    class FakeStore:
        def __init__(self):
            self.puts = []
            self.deleted = []

        def put_bytes(self, key, content):
            self.puts.append((key, content))
            return key

        def delete(self, key):
            self.deleted.append(key)

    store = FakeStore()
    import app.api.remote_training as remote_api

    monkeypatch.setattr(remote_api, "get_object_store", lambda: store)
    monkeypatch.setattr("app.services.object_store.get_object_store", lambda: store)
    monkeypatch.setattr(remote_api, "enqueue_video_processing", lambda _db, _video: "job-revision")

    valid_mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Revision Test OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Revision Test Firma", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        db.add(
            User(
                email="revision-admin@remote-test.com",
                full_name="Revision Admin",
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
            status="published",
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
        published = RemoteTrainingVideo(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            section_id=section.id,
            title="Yayımdaki temel İSG videosu",
            original_file_name="eski.mp4",
            content_type="video/mp4",
            storage_key="1/remote-basic-ohs/1/video-old.mp4",
            duration_seconds=456,
            revision_no=1,
            status="published",
            is_current=True,
        )
        db.add(published)
        db.commit()
        section_id = section.id
        published_id = published.id
        old_storage_key = published.storage_key

    login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "revision-admin@remote-test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    upload_url = f"/api/v1/trainings/remote/sections/{section_id}/videos"

    blocked_fresh_upload = remote_client.post(
        upload_url,
        headers=headers,
        data={"title": "Yanlış yeni ana video"},
        files={"file": ("yanlis.mp4", valid_mp4, "video/mp4")},
    )
    assert blocked_fresh_upload.status_code == 409, blocked_fresh_upload.text
    assert "Yeni sürüm" in blocked_fresh_upload.json()["detail"]

    revision_response = remote_client.post(
        upload_url,
        headers=headers,
        data={"title": "Güncel temel İSG videosu", "revision_of_id": str(published_id)},
        files={"file": ("guncel.mp4", valid_mp4, "video/mp4")},
    )
    assert revision_response.status_code == 201, revision_response.text
    revision = revision_response.json()
    assert revision["revision_of_id"] == published_id
    assert revision["revision_no"] == 2
    assert revision["is_current"] is False
    assert revision["status"] == "uploading"
    assert revision["processing_job_id"] == "job-revision"
    revision_id = revision["id"]
    revision_storage_key = store.puts[0][0]

    updated = remote_client.patch(
        f"/api/v1/trainings/remote/videos/{revision_id}",
        headers=headers,
        json={"title": "Güncel temel İSG videosu — kontrol"},
    )
    assert updated.status_code == 200, updated.text

    with SessionLocal() as db:
        old = db.get(RemoteTrainingVideo, published_id)
        assert old is not None
        assert old.status == "published"
        assert old.is_current is True
        assert db.get(RemoteTrainingVideo, revision_id).revision_of_id == published_id

    deleted = remote_client.delete(f"/api/v1/trainings/remote/videos/{revision_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert store.deleted == [revision_storage_key]
    assert store.puts and store.puts[0][0] == revision_storage_key

    with SessionLocal() as db:
        assert db.get(RemoteTrainingVideo, revision_id) is None
        old = db.get(RemoteTrainingVideo, published_id)
        assert old is not None
        assert old.storage_key == old_storage_key
        assert old.status == "published"
        assert old.is_current is True


def test_catalog_program_scope_is_fixed_to_its_package_sector():
    from app.models.remote_training import (
        REMOTE_SECTOR_CATALOG,
        RemoteTrainingCatalogPackage,
        RemoteTrainingProgram,
        RemoteTrainingProgramSector,
    )
    from app.services.remote_training import build_program_sector_catalog, program_sector_codes

    engine = _db()
    with Session(engine) as db:
        osgb, company, _branch, _employee, user = _scope_rows(db)
        package = RemoteTrainingCatalogPackage(
            osgb_id=osgb.id,
            code="battery-production-ohs",
            title="Akü-Batarya",
            status="published",
            created_by_id=user.id,
        )
        db.add(package)
        db.flush()
        program = RemoteTrainingProgram(
            osgb_id=osgb.id,
            company_id=company.id,
            source_catalog_package_id=package.id,
            source_catalog_code=package.code,
            title="Akü-Batarya",
            status="ready_for_review",
        )
        db.add(program)
        db.flush()
        # Older snapshots can retain the code while the package FK is absent.
        program.source_catalog_package_id = None
        # Simulate the old broken snapshot: common and battery were both
        # selected even though the copied sections are battery-specific.
        db.add_all(
            [
                RemoteTrainingProgramSector(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    program_id=program.id,
                    sector_code=code,
                    sector_name_snapshot=label,
                    is_enabled=code in {"common", "battery"},
                )
                for code, label, _description in REMOTE_SECTOR_CATALOG
            ]
        )
        db.flush()

        scope = build_program_sector_catalog(db, program)
        assert scope["catalog_fixed"] is True
        assert scope["catalog_sector_code"] == "battery"
        assert scope["selected_sector_codes"] == ["battery"]
        assert next(row for row in scope["sectors"] if row["code"] == "battery")["locked"] is True
        assert next(row for row in scope["sectors"] if row["code"] == "common")["locked"] is False
        assert next(row for row in scope["sectors"] if row["code"] == "battery")["enabled"] is True
        assert next(row for row in scope["sectors"] if row["code"] == "common")["enabled"] is False
        assert program_sector_codes(db, program.id) == {"battery"}


def test_catalog_program_rejects_mixed_scope_and_wrong_question(remote_client):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        Company,
        OsgbOrganization,
        TrainingQuestion,
        TrainingQuestionScope,
        User,
        UserRole,
    )
    from app.models.remote_training import (
        REMOTE_SECTOR_CATALOG,
        RemoteTrainingCatalogPackage,
        RemoteTrainingProgram,
        RemoteTrainingProgramSector,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Catalog Scope OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Catalog Scope Firma", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        user = User(
            email="catalog-scope-admin@remote-test.com",
            full_name="Catalog Scope Admin",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            company_id=company.id,
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(user)
        db.flush()
        package = RemoteTrainingCatalogPackage(
            osgb_id=osgb.id,
            code="battery-production-ohs",
            title="Akü-Batarya",
            status="published",
            created_by_id=user.id,
        )
        db.add(package)
        db.flush()
        program = RemoteTrainingProgram(
            osgb_id=osgb.id,
            company_id=company.id,
            source_catalog_package_id=package.id,
            source_catalog_code=package.code,
            title="Akü-Batarya",
            status="ready_for_review",
        )
        db.add(program)
        db.flush()
        db.add_all(
            [
                RemoteTrainingProgramSector(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    program_id=program.id,
                    sector_code=code,
                    sector_name_snapshot=label,
                    is_enabled=code in {"common", "battery"},
                )
                for code, label, _description in REMOTE_SECTOR_CATALOG
            ]
        )
        common_question = TrainingQuestion(
            question_code="CATALOG-COMMON-1",
            version=1,
            status="published",
            topic_code="common",
            topic_label="Ortak İSG",
            question_text="Ortak kapsam sorusu yeterince uzun metin",
            option_a="A seçeneği",
            option_b="B seçeneği",
            option_c="C seçeneği",
            option_d="D seçeneği",
            correct_option="A",
            answer_explanation="Ortak kapsam gerekçesi yeterince uzun metin",
            created_by_id=user.id,
        )
        battery_question = TrainingQuestion(
            question_code="CATALOG-BATTERY-1",
            version=1,
            status="published",
            topic_code="battery",
            topic_label="Akü-Batarya",
            question_text="Akü kapsam sorusu yeterince uzun metin",
            option_a="A seçeneği",
            option_b="B seçeneği",
            option_c="C seçeneği",
            option_d="D seçeneği",
            correct_option="A",
            answer_explanation="Akü kapsam gerekçesi yeterince uzun metin",
            created_by_id=user.id,
        )
        db.add_all([common_question, battery_question])
        db.flush()
        db.add_all(
            [
                TrainingQuestionScope(question_id=common_question.id, scope_type="common", scope_value="*"),
                TrainingQuestionScope(question_id=battery_question.id, scope_type="nace", scope_value="27.20"),
            ]
        )
        db.commit()
        company_id = company.id
        program_id = program.id
        common_question_id = common_question.id
        battery_question_id = battery_question.id

    login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "catalog-scope-admin@remote-test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    mixed = remote_client.put(
        f"/api/v1/trainings/remote/programs/{program_id}/sectors",
        headers=headers,
        json={"sector_codes": ["common", "battery"]},
    )
    assert mixed.status_code == 422, mixed.text
    assert "Akü" in mixed.json()["detail"]

    repaired = remote_client.put(
        f"/api/v1/trainings/remote/programs/{program_id}/sectors",
        headers=headers,
        json={"sector_codes": ["battery"]},
    )
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["selected_sector_codes"] == ["battery"]

    wrong_section = remote_client.post(
        f"/api/v1/trainings/remote/programs/{program_id}/sections",
        headers=headers,
        json={"title": "Yanlış ortak bölüm", "sector_code": "common"},
    )
    assert wrong_section.status_code == 422, wrong_section.text

    wrong_question = remote_client.post(
        f"/api/v1/trainings/remote/programs/{program_id}/exam/questions",
        headers=headers,
        json={"question_id": common_question_id, "position": 1, "sector_code": "battery"},
    )
    assert wrong_question.status_code == 422, wrong_question.text

    linked = remote_client.post(
        f"/api/v1/trainings/remote/programs/{program_id}/exam/questions",
        headers=headers,
        json={"question_id": battery_question_id, "position": 1, "sector_code": "battery"},
    )
    assert linked.status_code == 201, linked.text
    link_id = linked.json()["id"]
    removed = remote_client.delete(
        f"/api/v1/trainings/remote/programs/{program_id}/exam/questions/{link_id}",
        headers=headers,
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["deleted"] is True


def test_employee_panel_returns_all_published_assignments_not_notifications(remote_client, monkeypatch):
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, Employee, OsgbOrganization, User, UserRole
    from app.models.remote_training import (
        RemoteTrainingAssignment,
        RemoteTrainingAssignmentSector,
        RemoteTrainingCatalogPackage,
        RemoteTrainingEmployeeAccess,
        RemoteTrainingProgram,
        RemoteTrainingProgramSector,
    )

    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_enabled", True)
    monkeypatch.setattr(
        settings,
        "remote_basic_ohs_strict_policy_package_codes",
        "common-basic-ohs,battery-production-ohs",
    )
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_pilot_company_ids", "")

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Employee Panel OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Employee Panel Firma", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        employee = Employee(company_id=company.id, full_name="Panel Çalışanı", is_active=True)
        db.add(employee)
        db.flush()
        user = User(
            email="employee-panel@remote-test.com",
            full_name=employee.full_name,
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.READ_ONLY,
            company_id=company.id,
            osgb_id=osgb.id,
            password_change_required=False,
            is_active=True,
        )
        db.add(user)
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
        for code, title, sector in (
            ("common-basic-ohs", "Ortak Temel İSG", "common"),
            ("battery-production-ohs", "Akü-Batarya", "battery"),
        ):
            package = RemoteTrainingCatalogPackage(
                osgb_id=osgb.id,
                code=code,
                title=title,
                status="published",
            )
            db.add(package)
            db.flush()
            program = RemoteTrainingProgram(
                osgb_id=osgb.id,
                company_id=company.id,
                source_catalog_package_id=package.id,
                source_catalog_code=code,
                title=title,
                status="published",
                policy_mode="strict",
                completion_threshold_percent=100,
                passing_score=70,
                requires_final_exam=True,
                sequence_enforced=True,
                exam_gate_enforced=True,
            )
            db.add(program)
            db.flush()
            db.add(
                RemoteTrainingProgramSector(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    program_id=program.id,
                    sector_code=sector,
                    sector_name_snapshot=title,
                    is_enabled=True,
                )
            )
            assignment = RemoteTrainingAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                program_id=program.id,
                employee_id=employee.id,
                employee_name_snapshot=employee.full_name,
                workplace_name_snapshot="Panel işyeri",
            )
            db.add(assignment)
            db.flush()
            db.add(
                RemoteTrainingAssignmentSector(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    program_id=program.id,
                    assignment_id=assignment.id,
                    employee_id=employee.id,
                    sector_code=sector,
                    sector_name_snapshot=title,
                )
            )
        db.commit()

    login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "employee-panel@remote-test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    rows = remote_client.get("/api/v1/trainings/remote/my-assignments", headers=headers)
    assert rows.status_code == 200, rows.text
    output = rows.json()
    assert {row["program"]["title"] for row in output} == {"Ortak Temel İSG", "Akü-Batarya"}
    assert {tuple(row["sector_codes"]) for row in output} == {("common",), ("battery",)}
