"""Regression tests for the isolated Basic OHS remote-training layer."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine, select
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


def test_remote_assignment_display_uses_current_employee_name_after_personnel_edit(monkeypatch):
    from app.api import remote_training as remote_api
    from app.models.remote_training import RemoteTrainingAssignment

    engine = _db()
    with Session(engine) as db:
        _osgb, company, branch, employee, _user = _scope_rows(db)
        assignment = RemoteTrainingAssignment(
            company_id=company.id,
            branch_id=branch.id,
            program_id=1,
            employee_id=employee.id,
            employee_name_snapshot="Çalışan Test",
            status="not_started",
        )
        db.add(assignment)
        db.flush()
        monkeypatch.setattr(remote_api, "recalculate_assignment", lambda _db, _row: {})
        monkeypatch.setattr(remote_api, "assignment_sector_codes", lambda _db, _row: None)

        employee.full_name = "Ramiz GENÇTÜRK"
        output = remote_api._assignment_output(db, assignment)

        assert output["employee_name"] == "Ramiz GENÇTÜRK"
        assert assignment.employee_name_snapshot == "Çalışan Test"


def test_remote_video_validation_rejects_mismatched_content():
    from app.services.remote_training import validate_video_bytes

    valid_mp4_header = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
    validate_video_bytes(valid_mp4_header, extension=".mp4", original_name="ders.mp4")

    import pytest

    with pytest.raises(Exception):
        validate_video_bytes(b"not-a-video", extension=".mp4", original_name="ders.mp4")


def test_video_media_type_prefers_browser_compatible_extension():
    from types import SimpleNamespace

    from app.services.remote_training import _video_media_type

    assert _video_media_type(SimpleNamespace(
        original_file_name="ders.mp4",
        content_type="application/octet-stream",
    )) == "video/mp4"
    assert _video_media_type(SimpleNamespace(
        original_file_name="ders.webm",
        content_type="application/octet-stream",
    )) == "video/webm"


def test_direct_object_playback_is_opt_in_and_force_off_wins(monkeypatch):
    from app.core.config import remote_basic_ohs_direct_object_playback_active, settings

    monkeypatch.setattr(settings, "remote_basic_ohs_direct_object_playback_enabled", False)
    monkeypatch.setattr(settings, "remote_basic_ohs_direct_object_playback_force_off", False)
    assert remote_basic_ohs_direct_object_playback_active() is False

    monkeypatch.setattr(settings, "remote_basic_ohs_direct_object_playback_enabled", True)
    assert remote_basic_ohs_direct_object_playback_active() is True

    monkeypatch.setattr(settings, "remote_basic_ohs_direct_object_playback_force_off", True)
    assert remote_basic_ohs_direct_object_playback_active() is False


def test_video_response_redirects_to_r2_and_local_fallback_remains(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from fastapi.responses import FileResponse, RedirectResponse

    from app.core.config import settings
    from app.services import object_store as object_store_service
    from app.services import remote_training as service

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "object_storage_backend", "local")
    monkeypatch.setattr(settings, "remote_basic_ohs_direct_object_playback_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_direct_object_playback_force_off", False)
    monkeypatch.setattr(settings, "remote_basic_ohs_direct_object_playback_ttl_seconds", 3600)
    object_store_service.reset_object_store_for_tests()
    store = object_store_service.get_object_store()
    key = store.put_bytes("4/video/lesson.mp4", b"video-bytes")
    video = SimpleNamespace(
        storage_key=key,
        original_file_name="lesson.mp4",
        content_type="video/mp4",
    )
    calls = []
    monkeypatch.setattr(
        service,
        "presigned_object_read_url",
        lambda storage_key, *, expires_in_seconds: calls.append(
            (storage_key, expires_in_seconds)
        ) or "https://r2.example/signed-video",
    )

    redirected = service.response_for_video(video, SimpleNamespace(headers={}))
    assert isinstance(redirected, RedirectResponse)
    assert redirected.status_code == 307
    assert redirected.headers["location"] == "https://r2.example/signed-video"
    assert redirected.headers["cache-control"] == "private, no-store, max-age=0"
    assert calls == [(key, 3600)]

    local = service.response_for_video(
        video,
        SimpleNamespace(headers={"x-isg-local-video-fallback": "1"}),
    )
    assert isinstance(local, FileResponse)
    assert calls == [(key, 3600)]
    object_store_service.reset_object_store_for_tests()



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


def test_catalog_packages_receive_their_configured_automatic_exam_questions():
    from app.services.remote_training import (
        automatic_exam_items_for_package,
        automatic_exam_question_count,
    )

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
        expected_count = 20 if package_code == "working-at-height-ohs" else 10
        assert automatic_exam_question_count(package_code) == expected_count
        assert len(items) == expected_count
        assert len({item["question_code"] for item in items}) == expected_count
        assert len({item["topic_code"] for item in items}) == expected_count
        assert all(
            item["question_text"]
            and len(item["options"]) == 4
            and item["correct_option"] in "ABCD"
            and item["answer_explanation"]
            and item["sources"]
            for item in items
        )

    height_items = automatic_exam_items_for_package("working-at-height-ohs")
    assert len({item["topic_code"] for item in height_items}) == 20

    with pytest.raises(RuntimeError):
        automatic_exam_items_for_package("future-custom-package")


def test_automatic_final_exam_question_validation_is_independent():
    from types import SimpleNamespace

    from app.api.remote_training import (
        _automatic_final_exam_question_validation,
        _automatic_final_exam_validation,
    )

    good = SimpleNamespace(
        question_text="Geçerli final sorusu",
        options_json='{"A":"Birinci","B":"İkinci","C":"Üçüncü","D":"Dördüncü"}',
        correct_option="B",
    )
    broken = SimpleNamespace(
        question_text="",
        options_json='{"A":"A","B":"A","C":"C","D":"D"}',
        correct_option="X",
    )

    assert _automatic_final_exam_question_validation(good, 1) == []
    assert _automatic_final_exam_question_validation(broken, 2)
    assert _automatic_final_exam_validation([good, broken])


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


def test_strict_video_end_reconciles_only_the_final_tail():
    from app.services.remote_training import reconcile_strict_video_end

    reconciled = reconcile_strict_video_end(
        [[0.0, 103.0]],
        current_position=103.0,
        requested_position=110.0,
        duration=110.0,
    )
    assert reconciled == ([[0.0, 110.0]], 110.0, 110.0)

    # An ``ended`` payload cannot jump a learner from the middle of a video to
    # the end; the server must already have observed the final tail.
    assert reconcile_strict_video_end(
        [[0.0, 90.0]],
        current_position=90.0,
        requested_position=110.0,
        duration=110.0,
    ) is None


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


def test_strict_ended_progress_unlocks_the_next_video(remote_client, monkeypatch):
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import User, UserRole
    from app.models.remote_training import (
        RemoteTrainingAssignment,
        RemoteTrainingAssignmentSector,
        RemoteTrainingEmployeeAccess,
        RemoteTrainingProgram,
        RemoteTrainingSection,
        RemoteTrainingVideo,
        RemoteTrainingVideoProgress,
    )

    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_package_codes", "battery-production-ohs")
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_pilot_company_ids", "")

    with SessionLocal() as db:
        osgb, company, branch, employee, user = _scope_rows(db)
        user.hashed_password = get_password_hash("TestPass123!")
        user.company_id = company.id
        user.osgb_id = osgb.id
        user.password_change_required = False
        user.role = UserRole.READ_ONLY
        program = RemoteTrainingProgram(
            osgb_id=osgb.id,
            company_id=company.id,
            source_catalog_code="battery-production-ohs",
            title="Akü-Batarya",
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
        sections = []
        videos = []
        for index, title in enumerate(("Akü ilk ders", "Akü ikinci ders"), start=1):
            section = RemoteTrainingSection(
                osgb_id=osgb.id,
                company_id=company.id,
                program_id=program.id,
                sector_code="battery",
                title=title,
                order_index=index,
            )
            db.add(section)
            db.flush()
            video = RemoteTrainingVideo(
                osgb_id=osgb.id,
                company_id=company.id,
                program_id=program.id,
                section_id=section.id,
                title=title,
                original_file_name=f"aku-{index}.mp4",
                content_type="video/mp4",
                storage_key=f"{company.id}/remote-training/aku-{index}.mp4",
                duration_seconds=110,
                order_index=1,
                status="published",
                is_current=True,
            )
            db.add(video)
            db.flush()
            sections.append(section)
            videos.append(video)
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
            nace_description_snapshot="Akü üretimi",
            hazard_class_snapshot=company.hazard_class,
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
                sector_code="battery",
                sector_name_snapshot="Akü ve Otomotiv",
            )
        )
        db.add(
            RemoteTrainingEmployeeAccess(
                osgb_id=osgb.id,
                company_id=company.id,
                user_id=user.id,
                employee_id=employee.id,
                is_active=True,
            )
        )
        db.add(
            RemoteTrainingVideoProgress(
                company_id=company.id,
                program_id=program.id,
                assignment_id=assignment.id,
                section_id=sections[0].id,
                video_id=videos[0].id,
                employee_id=employee.id,
                last_position_seconds=103,
                watched_duration_seconds=103,
                watched_percentage=103 / 110 * 100,
                coverage_json="[[0,103]]",
                status="in_progress",
                last_access_at=datetime.utcnow(),
            )
        )
        db.commit()
        assignment_id = assignment.id
        first_video_id = videos[0].id
        second_video_id = videos[1].id

    login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "employee-remote@example.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    stale = remote_client.post(
        f"/api/v1/trainings/remote/assignments/{assignment_id}/videos/{first_video_id}/progress",
        headers=headers,
        json={"position_seconds": 0, "event_type": "start"},
    )
    assert stale.status_code == 200, stale.text
    assert stale.json()["accepted_position_seconds"] >= 103

    ended = remote_client.post(
        f"/api/v1/trainings/remote/assignments/{assignment_id}/videos/{first_video_id}/progress",
        headers=headers,
        json={"position_seconds": 110, "event_type": "ended"},
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "completed"
    assert ended.json()["watched_percentage"] == 100

    next_playback = remote_client.get(
        f"/api/v1/trainings/remote/videos/{second_video_id}/playback?assignment_id={assignment_id}",
        headers=headers,
    )
    assert next_playback.status_code == 200, next_playback.text


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
    height_package = next(row for row in rows if row["code"] == "working-at-height-ohs")
    assert height_package["section_count"] == 10
    assert height_package["automatic_exam_question_count"] == 20

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


def test_remote_catalog_published_package_accepts_additive_video_and_section(remote_client, monkeypatch):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, OsgbOrganization, User, UserRole
    from app.models.remote_training import RemoteTrainingCatalogPackage, RemoteTrainingCatalogVideo

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
    with SessionLocal() as db:
        package_row = db.get(RemoteTrainingCatalogPackage, package["id"])
        package_row.status = "published"
        package_row.revision_no = 4
        db.commit()

    added_section = remote_client.post(
        f"/api/v1/trainings/remote/catalog/packages/{package['id']}/sections",
        headers=headers,
        json={"code": "AKÜ-TEST", "title": "Akü ilave test bölümü"},
    )
    assert added_section.status_code == 201, added_section.text
    section_id = added_section.json()["id"]
    valid_mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16

    uploaded = remote_client.post(
        f"/api/v1/trainings/remote/catalog/sections/{section_id}/videos",
        headers=headers,
        data={"title": "AKÜ-TEST yeni videosu"},
        files={"file": ("aku-test.mp4", valid_mp4, "video/mp4")},
    )
    assert uploaded.status_code == 201, uploaded.text
    row = uploaded.json()
    assert row["status"] == "uploading"
    assert row["package_id"] == package["id"]
    assert row["revision_of_id"] is None
    assert store.puts and store.puts[0][0].startswith("remote-basic-ohs/catalog/")

    with SessionLocal() as db:
        catalog_video = db.get(RemoteTrainingCatalogVideo, row["id"])
        catalog_video.status = "ready_for_review"
        catalog_video.duration_seconds = 30
        db.commit()

    published = remote_client.post(
        f"/api/v1/trainings/remote/catalog/videos/{row['id']}/publish",
        headers=headers,
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"

    with SessionLocal() as db:
        package_row = db.get(RemoteTrainingCatalogPackage, package["id"])
        assert package_row.revision_no == 5

    second_upload = remote_client.post(
        f"/api/v1/trainings/remote/catalog/sections/{section_id}/videos",
        headers=headers,
        data={"title": "AKÜ-TEST silinecek taslak"},
        files={"file": ("aku-test-2.mp4", valid_mp4, "video/mp4")},
    )
    assert second_upload.status_code == 201, second_upload.text
    second_row = second_upload.json()
    deleted = remote_client.delete(f"/api/v1/trainings/remote/catalog/videos/{second_row['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert store.deleted == [store.puts[1][0]]


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


def test_remote_employee_account_provision_uses_username_and_username_login(remote_client):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import User, UserRole

    with SessionLocal() as db:
        osgb, company, _branch, employee, _employee_user = _scope_rows(db)
        employee.full_name = "Abdullah BOZKIR"
        admin = User(
            email="employee-provision-admin@remote-test.com",
            full_name="Employee Provision Admin",
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

    login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "employee-provision-admin@remote-test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    provisioned = remote_client.post(
        "/api/v1/trainings/remote/employee-access/provision",
        headers=admin_headers,
        json={"company_id": company_id, "employee_id": employee_id},
    )
    assert provisioned.status_code == 201, provisioned.text
    credentials = provisioned.json()
    assert credentials["username"] == "A.bozkir"
    assert credentials["password_change_required"] is True

    employee_login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": credentials["username"], "password": credentials["temporary_password"]},
    )
    assert employee_login.status_code == 200, employee_login.text
    employee_headers = {"Authorization": f"Bearer {employee_login.json()['access_token']}"}
    current_user = remote_client.get("/api/v1/auth/me", headers=employee_headers)
    assert current_user.status_code == 200, current_user.text
    assert current_user.json()["username"] == "A.bozkir"


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

    additive_upload = remote_client.post(
        upload_url,
        headers=headers,
        data={"title": "Yeni ana video"},
        files={"file": ("yeni.mp4", valid_mp4, "video/mp4")},
    )
    assert additive_upload.status_code == 201, additive_upload.text
    additive = additive_upload.json()
    assert additive["revision_of_id"] is None
    additive_storage_key = store.puts[0][0]
    deleted_additive = remote_client.delete(
        f"/api/v1/trainings/remote/videos/{additive['id']}",
        headers=headers,
    )
    assert deleted_additive.status_code == 200, deleted_additive.text
    assert store.deleted == [additive_storage_key]

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
    revision_storage_key = store.puts[1][0]

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
    assert store.deleted == [additive_storage_key, revision_storage_key]
    assert store.puts and store.puts[1][0] == revision_storage_key

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



def test_remote_certificate_adapter_uses_shared_label_and_signatory_context(monkeypatch):
    from app.models.remote_training import (
        RemoteTrainingAssignment,
        RemoteTrainingCertificate,
        RemoteTrainingProgram,
    )
    from app.services.remote_training import build_certificate_pdf

    captured = {}

    def fake_build_certificates_pdf(**kwargs):
        captured.update(kwargs)
        return b"%PDF-test"

    monkeypatch.setattr(
        "app.services.training_pdfs.build_certificates_pdf",
        fake_build_certificates_pdf,
    )

    engine = _db()
    with Session(engine) as db:
        _osgb, company, branch, employee, _user = _scope_rows(db)
        company.authorized_person = "İşveren Test"
        program = RemoteTrainingProgram(
            company_id=company.id,
            title="Yüksekte Çalışma İSG Paketi",
            instructor_name="Uzman Test",
            instructor_qualification="A Sınıfı İş Güvenliği Uzmanı",
            total_duration_seconds=3600,
            passing_score=70,
        )
        db.add(program)
        db.flush()
        assignment = RemoteTrainingAssignment(
            company_id=company.id,
            branch_id=branch.id,
            program_id=program.id,
            employee_id=employee.id,
            employee_name_snapshot=employee.full_name,
            workplace_name_snapshot="Merkez İşyeri",
            sgk_registration_number_snapshot="SGK-BRANCH-1",
            nace_code_snapshot="46.83.06",
            nace_description_snapshot="Faaliyet alanı",
            hazard_class_snapshot="Tehlikeli",
            status="completed",
            completed_at=datetime.utcnow(),
        )
        db.add(assignment)
        db.flush()
        certificate = RemoteTrainingCertificate(
            company_id=company.id,
            program_id=program.id,
            assignment_id=assignment.id,
            employee_id=employee.id,
            employee_name_snapshot=employee.full_name,
            company_name_snapshot=company.name,
            workplace_name_snapshot=assignment.workplace_name_snapshot,
            sgk_registration_number_snapshot=assignment.sgk_registration_number_snapshot,
            nace_code_snapshot=assignment.nace_code_snapshot,
            nace_description_snapshot=assignment.nace_description_snapshot,
            hazard_class_snapshot=assignment.hazard_class_snapshot,
            training_name=program.title,
            training_type="Basic Occupational Health and Safety Training",
            training_duration_seconds=program.total_duration_seconds,
            training_date=date.today(),
            instructor_name_snapshot=program.instructor_name,
            examination_score=80,
            certificate_number="ROHS-TEST-0001",
            verification_code="REMOTE-TEST-CERTIFICATE",
        )
        db.add(certificate)
        db.flush()

        assert build_certificate_pdf(db, certificate) == b"%PDF-test"

    training = captured["training"]
    assert captured["company_name"] == "Remote Test Firma"
    assert training.training_type == "Uzaktan Eğitim"
    assert training.delivery_method == "Uzaktan Eğitim"
    assert training.instructor_name == "Uzman Test"
    assert training.instructor_qualification == "A Sınıfı İş Güvenliği Uzmanı"
    assert training.employer_representative == "İşveren Test"
    assert training.passing_score == 70


def test_remote_content_permission_separates_osgb_admin_and_expert():
    from fastapi import HTTPException

    from app.api.remote_training import (
        _assert_catalog_content_editor,
        _catalog_content_package_for_manager,
    )
    from app.models.entities import OsgbOrganization, User, UserRole
    from app.models.remote_training import RemoteTrainingCatalogPackage
    from app.services.remote_training import is_catalog_content_manager, is_manager

    engine = _db()
    with Session(engine) as db:
        osgb = OsgbOrganization(name="Permission Test OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        admin = User(
            email="osgb-admin@example.com",
            full_name="OSGB Yönetici",
            hashed_password="x",
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            company_id=None,
            is_active=True,
        )
        expert = User(
            email="expert@example.com",
            full_name="İSG Uzmanı",
            hashed_password="x",
            role=UserRole.SAFETY_SPECIALIST,
            osgb_id=osgb.id,
            is_active=True,
        )
        global_admin = User(
            email="global-admin@example.com",
            full_name="Global Yönetici",
            hashed_password="x",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add_all([admin, expert, global_admin])
        db.flush()

        assert is_manager(expert)
        assert not is_catalog_content_manager(expert)
        with pytest.raises(HTTPException) as error:
            _assert_catalog_content_editor(db, expert)
        assert error.value.status_code == 403
        assert not is_catalog_content_manager(global_admin)
        with pytest.raises(HTTPException) as error:
            _assert_catalog_content_editor(db, global_admin)
        assert error.value.status_code == 403

        package = RemoteTrainingCatalogPackage(
            osgb_id=osgb.id,
            code="osgb-only-package",
            title="OSGB Özel Paket",
            status="draft",
        )
        db.add(package)
        db.flush()
        with pytest.raises(HTTPException) as error:
            _catalog_content_package_for_manager(db, global_admin, package.id)
        assert error.value.status_code == 403

        _assert_catalog_content_editor(db, admin)


def test_shared_catalog_preview_is_allowed_for_expert_and_old_video_revisions_are_hidden():
    from app.api.remote_training import _catalog_package_output
    from app.models.entities import OsgbOrganization, User, UserRole
    from app.models.remote_training import (
        RemoteTrainingCatalogPackage,
        RemoteTrainingCatalogSection,
        RemoteTrainingCatalogVideo,
    )
    from app.services.remote_training import (
        create_catalog_playback_token,
        decode_catalog_playback_token,
    )

    engine = _db()
    with Session(engine) as db:
        osgb = OsgbOrganization(name="Shared Preview OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        expert = User(
            email="shared-preview-expert@example.com",
            full_name="Önizleme Uzmanı",
            hashed_password="x",
            role=UserRole.SAFETY_SPECIALIST,
            osgb_id=osgb.id,
            is_active=True,
        )
        package = RemoteTrainingCatalogPackage(
            osgb_id=None,
            code="food-production-ohs",
            title="Gıda",
            status="published",
        )
        db.add_all([expert, package])
        db.flush()
        section = RemoteTrainingCatalogSection(
            package_id=package.id,
            code="GID-01",
            title="Gıda üretimi",
            status="active",
        )
        db.add(section)
        db.flush()
        old_video = RemoteTrainingCatalogVideo(
            package_id=package.id,
            section_id=section.id,
            title="GID-01_CORE_FULL",
            revision_no=1,
            is_current=False,
            status="unpublished",
            original_file_name="gid-01-eski.mp4",
            content_type="video/mp4",
            file_size_bytes=100,
            duration_seconds=139,
            storage_key="catalog/shared/gid-01-old.mp4",
        )
        db.add(old_video)
        db.flush()
        current_video = RemoteTrainingCatalogVideo(
            package_id=package.id,
            section_id=section.id,
            revision_of_id=old_video.id,
            title="GID-01_CORE_FULL",
            revision_no=2,
            is_current=True,
            status="published",
            original_file_name="gid-01-guncel.mp4",
            content_type="video/mp4",
            file_size_bytes=100,
            duration_seconds=139,
            storage_key="catalog/shared/gid-01-current.mp4",
        )
        db.add(current_video)
        db.commit()

        token = create_catalog_playback_token(user=expert, video=current_video)
        decoded_user, decoded_video = decode_catalog_playback_token(
            db, token, current_video.id
        )
        assert decoded_user.id == expert.id
        assert decoded_video.id == current_video.id

        output = _catalog_package_output(db, package, detail=True)
        assert output["video_count"] == 1
        assert output["published_video_count"] == 1
        assert len(output["sections"][0]["videos"]) == 1
        assert output["sections"][0]["videos"][0]["id"] == current_video.id


def test_manager_can_delete_assignment_and_training_history(remote_client):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import User, UserRole
    from app.models.remote_training import (
        RemoteTrainingAssignment,
        RemoteTrainingAuditLog,
        RemoteTrainingEmployeeAccess,
        RemoteTrainingProgram,
    )

    with SessionLocal() as db:
        osgb, company, _branch, employee, employee_user = _scope_rows(db)
        employee_user.hashed_password = get_password_hash("TestPass123!")
        employee_user.company_id = company.id
        employee_user.osgb_id = osgb.id
        employee_user.password_change_required = False
        manager = User(
            email="training-manager@remote-test.com",
            full_name="Eğitim Yöneticisi",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            company_id=company.id,
            is_active=True,
        )
        program = RemoteTrainingProgram(
            osgb_id=osgb.id,
            company_id=company.id,
            title="Ortak Temel İSG",
            status="published",
            requires_final_exam=False,
        )
        db.add_all([manager, program])
        db.flush()
        db.add(
            RemoteTrainingEmployeeAccess(
                osgb_id=osgb.id,
                company_id=company.id,
                user_id=employee_user.id,
                employee_id=employee.id,
                is_active=True,
            )
        )
        db.commit()
        program_id = program.id
        employee_id = employee.id

    manager_login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "training-manager@remote-test.com", "password": "TestPass123!"},
    )
    assert manager_login.status_code == 200, manager_login.text
    manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}

    assigned = remote_client.post(
        f"/api/v1/trainings/remote/programs/{program_id}/assign",
        headers=manager_headers,
        json={"employee_ids": [employee_id]},
    )
    assert assigned.status_code == 200, assigned.text
    assignment_id = assigned.json()["created"][0]["id"]

    employee_login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "employee-remote@example.com", "password": "TestPass123!"},
    )
    assert employee_login.status_code == 200, employee_login.text
    employee_headers = {"Authorization": f"Bearer {employee_login.json()['access_token']}"}
    assert len(remote_client.get("/api/v1/trainings/remote/my-assignments", headers=employee_headers).json()) == 1

    deleted = remote_client.delete(
        f"/api/v1/trainings/remote/programs/{program_id}/assignments/{assignment_id}",
        headers=manager_headers,
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True

    assert remote_client.get("/api/v1/trainings/remote/my-assignments", headers=employee_headers).json() == []
    assert remote_client.get(
        f"/api/v1/trainings/remote/assignments/{assignment_id}",
        headers=employee_headers,
    ).status_code == 404

    with SessionLocal() as db:
        stored = db.get(RemoteTrainingAssignment, assignment_id)
        assert stored is None
        audit_row = db.scalar(
            select(RemoteTrainingAuditLog).where(
                RemoteTrainingAuditLog.action == "program_assignment_deleted",
                RemoteTrainingAuditLog.entity_id == str(assignment_id),
            )
        )
        assert audit_row is not None

    assert remote_client.delete(
        f"/api/v1/trainings/remote/programs/{program_id}/assignments/{assignment_id}",
        headers=manager_headers,
    ).status_code == 404


def test_company_certificate_hub_lists_failed_records_exports_and_bulk_deletes(remote_client):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import User, UserRole
    from app.models.remote_training import (
        RemoteTrainingAssignment,
        RemoteTrainingExamAttempt,
        RemoteTrainingEmployeeAccess,
        RemoteTrainingProgram,
    )

    with SessionLocal() as db:
        osgb, company, _branch, employee, employee_user = _scope_rows(db)
        employee_user.hashed_password = get_password_hash("TestPass123!")
        employee_user.company_id = company.id
        employee_user.osgb_id = osgb.id
        employee_user.password_change_required = False
        manager = User(
            email="certificate-hub-manager@remote-test.com",
            full_name="Belge Rapor Yöneticisi",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            company_id=company.id,
            is_active=True,
        )
        program = RemoteTrainingProgram(
            osgb_id=osgb.id,
            company_id=company.id,
            title="Ortak Temel İSG",
            status="published",
            requires_final_exam=True,
        )
        db.add_all([manager, program])
        db.flush()
        db.add(
            RemoteTrainingEmployeeAccess(
                osgb_id=osgb.id,
                company_id=company.id,
                user_id=employee_user.id,
                employee_id=employee.id,
                is_active=True,
            )
        )
        db.commit()
        program_id = program.id
        company_id = company.id
        employee_id = employee.id

    manager_login = remote_client.post(
        "/api/v1/auth/login",
        json={"email": "certificate-hub-manager@remote-test.com", "password": "TestPass123!"},
    )
    assert manager_login.status_code == 200, manager_login.text
    manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}

    assigned = remote_client.post(
        f"/api/v1/trainings/remote/programs/{program_id}/assign",
        headers=manager_headers,
        json={"employee_ids": [employee_id]},
    )
    assert assigned.status_code == 200, assigned.text
    assignment_id = assigned.json()["created"][0]["id"]
    with SessionLocal() as db:
        db.add(
            RemoteTrainingExamAttempt(
                company_id=company_id,
                program_id=program_id,
                assignment_id=assignment_id,
                employee_id=employee_id,
                attempt_no=1,
                question_ids_json="[1]",
                answers_json='{"1":"A"}',
                score=40,
                passed=False,
                submitted_at=datetime.utcnow(),
            )
        )
        db.commit()

    failed = remote_client.get(
        f"/api/v1/trainings/remote/certificates?company_id={company_id}&status=failed",
        headers=manager_headers,
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()[0]["report_status"] == "failed"
    assert failed.json()[0]["examination_score"] == 40

    xlsx = remote_client.get(
        f"/api/v1/trainings/remote/certificates/export.xlsx?company_id={company_id}&status=failed",
        headers=manager_headers,
    )
    assert xlsx.status_code == 200, xlsx.text
    assert xlsx.content.startswith(b"PK")

    pdf = remote_client.get(
        f"/api/v1/trainings/remote/certificates/export.pdf?company_id={company_id}&status=failed",
        headers=manager_headers,
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")

    deleted = remote_client.request(
        "DELETE",
        "/api/v1/trainings/remote/certificates/records",
        headers=manager_headers,
        json={"assignment_ids": [assignment_id]},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted_count"] == 1
    assert remote_client.get(
        f"/api/v1/trainings/remote/certificates?company_id={company_id}",
        headers=manager_headers,
    ).json() == []

def test_remote_video_range_parser_supports_browser_ranges():
    from fastapi import HTTPException

    from app.services.remote_training import _parse_video_range

    assert _parse_video_range(None, 100) is None
    assert _parse_video_range("bytes=0-9", 100) == (0, 9)
    assert _parse_video_range("bytes=90-", 100) == (90, 99)
    assert _parse_video_range("bytes=-10", 100) == (90, 99)

    with pytest.raises(HTTPException) as error:
        _parse_video_range("bytes=100-", 100)
    assert error.value.status_code == 416
