"""Remote documents use NACE lesson hours, independently of video length."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import Request
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import Company, Employee, OsgbOrganization, User, UserRole
from app.models.remote_training import RemoteTrainingAssignment, RemoteTrainingProgram
from app.services import remote_training as service


@pytest.fixture
def scope():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        osgb = OsgbOrganization(name="Süre Test OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(
            name="Süre Test İşyeri", osgb_id=osgb.id,
            sgk_registry_no="SGK-DURATION-1", nace_code="41.20.02",
            hazard_class="Çok Tehlikeli", is_active=True,
        )
        db.add(company)
        db.flush()
        employee = Employee(company_id=company.id, full_name="Çalışan Test", is_active=True)
        program = RemoteTrainingProgram(
            company_id=company.id, osgb_id=osgb.id,
            title="Temel İş Sağlığı ve Güvenliği Eğitimi", status="published",
            total_duration_seconds=60, instructor_name="Uzman Test",
        )
        user = User(
            email="duration-admin@example.com", full_name="Yönetici Test",
            hashed_password="x", role=UserRole.GLOBAL_ADMIN, is_active=True,
        )
        db.add_all([employee, program, user])
        db.flush()
        assignment = RemoteTrainingAssignment(
            company_id=company.id, osgb_id=osgb.id, program_id=program.id,
            employee_id=employee.id, employee_name_snapshot=employee.full_name,
            workplace_name_snapshot=company.name,
            sgk_registration_number_snapshot=company.sgk_registry_no,
            nace_code_snapshot="41.20.02",
            nace_description_snapshot="İkamet amaçlı binaların inşaatı",
            hazard_class_snapshot="Çok Tehlikeli", status="completed",
            completed_at=datetime(2026, 10, 8),
        )
        db.add(assignment)
        db.flush()
        yield SimpleNamespace(
            db=db, company=company, employee=employee, program=program,
            assignment=assignment, user=user,
        )
    engine.dispose()


@pytest.mark.parametrize("video_seconds", [60, 108000])
@pytest.mark.parametrize("nace,hazard,hours", [
    ("69.20.01", "Az Tehlikeli", 8),
    ("46.83.06", "Tehlikeli", 12),
    ("41.20.02", "Çok Tehlikeli", 16),
])
def test_new_certificate_uses_nace_lesson_hours(scope, video_seconds, nace, hazard, hours):
    scope.assignment.nace_code_snapshot = nace
    scope.assignment.hazard_class_snapshot = hazard
    scope.program.total_duration_seconds = video_seconds

    certificate = service.ensure_certificate(scope.db, scope.assignment)

    # A lesson hour includes 45 minutes teaching and 15 minutes break.
    assert certificate.training_duration_seconds == hours * 3600
    assert scope.program.total_duration_seconds == video_seconds


@pytest.mark.parametrize("builder", ["base", "identity_logo_extension"])
@pytest.mark.parametrize("nace,hazard,hours", [
    ("69.20.01", "Az Tehlikeli", 8),
    ("46.83.06", "Tehlikeli", 12),
    ("41.20.02", "Çok Tehlikeli", 16),
])
def test_existing_pdf_uses_snapshot_hours_without_rewriting_history(scope, builder, nace, hazard, hours):
    from app.services.remote_training_document_extension import build_remote_certificate_pdf

    scope.assignment.nace_code_snapshot = nace
    scope.assignment.hazard_class_snapshot = hazard
    certificate = service.ensure_certificate(scope.db, scope.assignment)
    certificate.training_duration_seconds = 60
    # Current company changes must not change the assigned training's scope.
    scope.company.nace_code = "01.11.07"
    scope.company.hazard_class = "Tehlikeli"
    scope.db.flush()

    build_pdf = service.build_certificate_pdf if builder == "base" else build_remote_certificate_pdf
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(build_pdf(scope.db, certificate))).pages)

    assert f"Süre: {hours} DERS SAAT" in text
    assert f"Tehlike Sınıfı: {hazard}" in text
    assert certificate.training_duration_seconds == 60


def test_combined_packages_count_the_basic_training_duration_once(scope):
    certificate = service.ensure_certificate(scope.db, scope.assignment)
    certificate.training_duration_seconds = 60
    second = SimpleNamespace(**{
        key: value for key, value in certificate.__dict__.items()
        if not key.startswith("_")
    })
    second.training_name = "İşe ve İşyerine Özgü Sektör Paketi"
    second.training_duration_seconds = 108000

    combined = service.combined_remote_certificate_view([certificate, second])

    assert combined.training_duration_seconds == 57600
    assert second.training_name in combined.training_name
    assert certificate.training_duration_seconds == 60
    assert second.training_duration_seconds == 108000


def test_company_snapshot_uses_exact_nace_hazard_instead_of_stale_company_label(scope):
    scope.company.hazard_class = "Az Tehlikeli"

    snapshot = service.company_snapshot(scope.db, scope.company.id)

    assert snapshot["nace_code"] == "41.20.02"
    assert snapshot["hazard_class"] == "Çok Tehlikeli"
    assert scope.company.hazard_class == "Az Tehlikeli"


def test_certificate_json_and_pdf_report_the_same_hours_for_existing_record(scope, monkeypatch):
    from app.api import remote_training as remote_api
    from app.core.config import settings

    monkeypatch.setattr(settings, "remote_basic_ohs_training_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_training_force_off", False)
    certificate = service.ensure_certificate(scope.db, scope.assignment)
    certificate.training_duration_seconds = 60

    result = remote_api.get_remote_certificate(scope.assignment.id, db=scope.db, user=scope.user)

    assert result["training_duration_seconds"] == 57600
    assert result["training_duration_hours"] == 16
    assert certificate.training_duration_seconds == 60


def test_unknown_legacy_nace_uses_recorded_hazard_hours(scope):
    scope.assignment.nace_code_snapshot = "62.01.01"
    scope.assignment.hazard_class_snapshot = "Az Tehlikeli"

    certificate = service.ensure_certificate(scope.db, scope.assignment)

    assert certificate.training_duration_seconds == 28800


def test_exact_nace_overrides_stale_assignment_hazard_for_duration(scope):
    scope.assignment.hazard_class_snapshot = "Az Tehlikeli"

    certificate = service.ensure_certificate(scope.db, scope.assignment)

    assert certificate.training_duration_seconds == 57600


def test_public_verification_uses_the_same_duration_as_the_document(scope, monkeypatch):
    from app.api import remote_training as remote_api
    from app.core.config import settings

    monkeypatch.setattr(settings, "remote_basic_ohs_training_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_training_force_off", False)
    certificate = service.ensure_certificate(scope.db, scope.assignment)
    certificate.training_duration_seconds = 60

    result = remote_api.verify_remote_certificate(certificate.verification_code, db=scope.db)

    assert result["training_duration_hours"] == 16
    assert result["training_duration_seconds"] == 57600
    assert result["employee_name"] != scope.employee.full_name
    assert certificate.training_duration_seconds == 60


def test_missing_valid_classification_cannot_fall_back_to_video_hours(scope):
    scope.assignment.nace_code_snapshot = "99.99.99"
    scope.assignment.hazard_class_snapshot = "Bilinmiyor"

    assert service.ensure_certificate(scope.db, scope.assignment) is None


def test_unfinished_assignment_does_not_receive_a_certificate_from_planned_hours(scope):
    scope.assignment.status = "not_started"
    scope.assignment.completed_at = None

    assert service.ensure_certificate(scope.db, scope.assignment) is None


def test_unknown_classification_preserves_completed_exam_without_issuing_document(scope, monkeypatch):
    from sqlalchemy import select
    from app.api import remote_training as remote_api
    from app.core.config import settings
    from app.models.entities import TrainingQuestion
    from app.models.remote_training import (
        RemoteTrainingExamAttempt, RemoteTrainingProgramQuestion,
        RemoteTrainingSection, RemoteTrainingVideo, RemoteTrainingVideoProgress,
    )
    from app.schemas.remote_training import RemoteExamSubmit

    monkeypatch.setattr(settings, "remote_basic_ohs_training_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_training_force_off", False)
    scope.assignment.nace_code_snapshot = "99.99.99"
    scope.assignment.hazard_class_snapshot = "Bilinmiyor"
    scope.assignment.status = "in_progress"
    scope.assignment.completed_at = None
    section = RemoteTrainingSection(
        company_id=scope.company.id, program_id=scope.program.id,
        title="Temel bölüm", is_required=True,
    )
    question = TrainingQuestion(
        question_code="DURATION-EXAM-1", version=1, status="published",
        topic_code="basic", topic_label="Temel İSG",
        question_text="Tehlike fark edildiğinde ne yapılır?",
        option_a="Bildirilir", option_b="Gizlenir", option_c="Ertelenir", option_d="Yok sayılır",
        correct_option="A", answer_explanation="Tehlike bildirilmelidir.",
        created_by_id=scope.user.id,
    )
    scope.db.add_all([section, question])
    scope.db.flush()
    video = RemoteTrainingVideo(
        company_id=scope.company.id, program_id=scope.program.id,
        section_id=section.id, title="Temel video", original_file_name="ders.mp4",
        content_type="video/mp4", storage_key="duration-test/ders.mp4",
        duration_seconds=60, status="published", is_current=True,
    )
    scope.db.add(video)
    scope.db.flush()
    scope.db.add_all([
        RemoteTrainingVideoProgress(
            company_id=scope.company.id, program_id=scope.program.id,
            assignment_id=scope.assignment.id, employee_id=scope.employee.id,
            section_id=section.id, video_id=video.id, status="completed",
            watched_duration_seconds=60, watched_percentage=100,
        ),
        RemoteTrainingProgramQuestion(
            company_id=scope.company.id, program_id=scope.program.id,
            question_id=question.id, position=1,
        ),
    ])
    scope.db.commit()

    result = remote_api.submit_remote_exam(
        scope.assignment.id, RemoteExamSubmit(answers={str(question.id): "A"}),
        Request({"type": "http", "client": ("127.0.0.1", 12345)}),
        db=scope.db, user=scope.user,
    )
    scope.db.rollback()

    assert result["passed"] is True
    assert result["certificate_id"] is None
    assert scope.db.scalar(select(RemoteTrainingExamAttempt)).passed is True
    assert scope.db.get(RemoteTrainingAssignment, scope.assignment.id).status == "completed"


@pytest.mark.parametrize("title", [
    "Yüksekte Çalışma İSG Paketi",
    "Ortak Temel İSG + Yüksekte Çalışma İSG Paketi",
])
def test_package_title_cannot_override_basic_course_lesson_hours(scope, title, monkeypatch):
    from app.services.remote_training_document_extension import build_remote_certificate_pdf
    from app.services import training_pdfs, training_runtime_patches

    # Exercise the same premium/height renderer dispatch installed at startup.
    monkeypatch.setattr(training_pdfs, "_draw_certificate_page", training_pdfs._draw_certificate_page)
    training_runtime_patches._patch_certificate_renderer()

    scope.program.title = title
    certificate = service.ensure_certificate(scope.db, scope.assignment)
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(build_remote_certificate_pdf(scope.db, certificate))).pages)

    assert "Süre: 16 DERS SAAT" in text
    assert "TEMEL İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİMİ KATILIM BELGESİ" in text
