from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import Base, get_db
from app.models import entities  # noqa: F401
from app.models import remote_training as _remote_training_models  # noqa: F401
from app.models.entities import (
    Company,
    Employee,
    HealthFitnessStatus,
    HealthRecord,
    HealthRecordType,
    Notification,
    NotificationType,
    OsgbOrganization,
    TrainingParticipant,
    TrainingSession,
    TrainingStatus,
    User,
    UserRole,
)
from app.models.remote_training import (
    RemoteTrainingAssignment,
    RemoteTrainingCertificate,
    RemoteTrainingEmployeeAccess,
    RemoteTrainingExamAttempt,
    RemoteTrainingProgram,
    RemoteTrainingSection,
    RemoteTrainingVideo,
    RemoteTrainingVideoProgress,
)
from app.api.self_service import (
    _assert_self_service_user,
    _certificate_summary,
    _own_classroom_certificate,
    _own_remote_certificate,
    _resolve_employee_scope,
    build_own_classroom_certificate_pdf,
    build_own_remote_certificate_pdf,
    build_self_service_payload,
    router,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _seed(db: Session):
    osgb = OsgbOrganization(name="Self Servis OSGB", is_active=True)
    other_osgb = OsgbOrganization(name="Diğer OSGB", is_active=True)
    db.add_all([osgb, other_osgb])
    db.flush()

    company = Company(name="Self Servis İşyeri", osgb_id=osgb.id, is_active=True)
    other_company = Company(name="Başka İşyeri", osgb_id=other_osgb.id, is_active=True)
    db.add_all([company, other_company])
    db.flush()

    employee = Employee(
        company_id=company.id,
        full_name="Ayşe Yılmaz",
        job_title="Kaynakçı",
        department="Üretim",
        start_date=date(2024, 1, 15),
        is_active=True,
    )
    db.add(employee)
    db.flush()

    user = User(
        email="ayse.employee@example.com",
        full_name="Ayşe Yılmaz",
        hashed_password="hash",
        role=UserRole.READ_ONLY,
        company_id=company.id,
        osgb_id=osgb.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    mapping = RemoteTrainingEmployeeAccess(
        company_id=company.id,
        osgb_id=osgb.id,
        user_id=user.id,
        employee_id=employee.id,
        is_active=True,
    )
    db.add(mapping)
    db.flush()
    return osgb, company, other_company, employee, user, mapping


@pytest.fixture()
def certificate_scope(db, monkeypatch):
    for name in ("employee_self_service", "remote_basic_ohs_training"):
        monkeypatch.setattr(settings, f"{name}_enabled", True)
        monkeypatch.setattr(settings, f"{name}_force_off", False)
    return _seed(db)


def _classroom(db, company, employee, user, **changes):
    values = dict(
        company_id=company.id, title="Katılım Eğitimi", start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1), hazard_class="Az Tehlikeli", instructor_name="Eğitici",
        status=TrainingStatus.COMPLETED, attendance_verified=True, created_by_id=user.id,
        evaluation_method="Katılım esası",
    )
    values.update(changes)
    training = TrainingSession(**values)
    db.add(training)
    db.flush()
    participant = TrainingParticipant(training_id=training.id, employee_id=employee.id, attended=True)
    db.add(participant)
    db.flush()
    return training, participant


def _remote(db, company, employee, **changes):
    program = RemoteTrainingProgram(company_id=company.id, title="Uzaktan Eğitim", status="published")
    db.add(program)
    db.flush()
    values = dict(
        company_id=company.id, program_id=program.id, employee_id=employee.id,
        employee_name_snapshot=employee.full_name, workplace_name_snapshot=company.name,
        sgk_registration_number_snapshot="SGK-1", nace_code_snapshot="46.83.06",
        nace_description_snapshot="Toptan ticaret", hazard_class_snapshot="Tehlikeli",
        status="in_progress",
    )
    values.update(changes)
    assignment = RemoteTrainingAssignment(**values)
    db.add(assignment)
    db.flush()
    return assignment


def _remote_progress(db, assignment, *, video_complete=True, passed=True):
    section = RemoteTrainingSection(company_id=assignment.company_id, program_id=assignment.program_id,
                                    title="Ders", status="active")
    db.add(section)
    db.flush()
    video = RemoteTrainingVideo(
        company_id=assignment.company_id, program_id=assignment.program_id, section_id=section.id,
        title="Video", status="published", original_file_name="video.mp4", content_type="video/mp4",
        storage_key=f"test/{assignment.id}.mp4", duration_seconds=60,
    )
    db.add(video)
    db.flush()
    db.add(RemoteTrainingVideoProgress(
        company_id=assignment.company_id, program_id=assignment.program_id, assignment_id=assignment.id,
        section_id=section.id, video_id=video.id, employee_id=assignment.employee_id,
        status="completed" if video_complete else "in_progress", watched_percentage=100 if video_complete else 50,
    ))
    if passed is not None:
        db.add(RemoteTrainingExamAttempt(
            company_id=assignment.company_id, program_id=assignment.program_id, assignment_id=assignment.id,
            employee_id=assignment.employee_id, attempt_no=1, question_ids_json="[]", answers_json="{}",
            score=80 if passed else 20, passed=passed, submitted_at=datetime.utcnow(),
        ))
    db.flush()


def _client(db, user):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_self_service_is_fail_closed_by_default(db: Session, monkeypatch):
    _, _, _, _, user, _ = _seed(db)
    monkeypatch.setattr(settings, "employee_self_service_enabled", False)
    monkeypatch.setattr(settings, "employee_self_service_force_off", False)

    with pytest.raises(HTTPException) as exc:
        _assert_self_service_user(user)
    assert exc.value.status_code == 404


def test_self_service_is_read_only_role_only(db: Session, monkeypatch):
    _, company, _, _, _, _ = _seed(db)
    admin = User(
        email="admin.self-service@example.com",
        full_name="OSGB Yönetici",
        hashed_password="hash",
        role=UserRole.COMPANY_ADMIN,
        company_id=company.id,
        is_active=True,
    )
    db.add(admin)
    db.flush()
    monkeypatch.setattr(settings, "employee_self_service_enabled", True)
    monkeypatch.setattr(settings, "employee_self_service_force_off", False)

    with pytest.raises(HTTPException) as exc:
        _assert_self_service_user(admin)
    assert exc.value.status_code == 403


def test_self_service_uses_explicit_mapping_and_minimizes_health_data(db: Session, monkeypatch):
    osgb, company, other_company, employee, user, mapping = _seed(db)
    monkeypatch.setattr(settings, "employee_self_service_enabled", True)
    monkeypatch.setattr(settings, "employee_self_service_force_off", False)

    _, resolved_company, resolved_employee, branch = _resolve_employee_scope(db, user)
    assert resolved_company.id == company.id
    assert resolved_employee.id == employee.id
    assert branch is None

    health = HealthRecord(
        company_id=company.id,
        employee_id=employee.id,
        record_type=HealthRecordType.PERIODIC_EXAM,
        examination_date=date(2026, 1, 10),
        next_examination_date=date(2027, 1, 10),
        fitness_status=HealthFitnessStatus.FIT,
        summary="klinik özet gizli",
        confidential_note="gizli not",
        restrictions="gizli kısıt",
        created_by_id=user.id,
    )
    db.add(health)
    db.flush()
    payload = build_self_service_payload(
        db,
        user=user,
        company=resolved_company,
        employee=resolved_employee,
        branch=branch,
    )
    assert payload["scope"]["company_id"] == company.id
    assert payload["employee"]["id"] == employee.id
    assert payload["health"]["next_examination_date"] == "2027-01-10"
    assert payload["health"]["details_included"] is False
    assert "confidential_note" not in payload["health"]
    assert "fitness_status" not in payload["health"]
    assert payload["privacy"]["cross_employee_data"] is False
    assert payload["capabilities"]["can_write"] is False

    # A company binding changed away from the explicit mapping is rejected;
    # no name-based fallback can recover access.
    user.company_id = other_company.id
    with pytest.raises(HTTPException) as exc:
        _resolve_employee_scope(db, user)
    assert exc.value.status_code == 403
    assert mapping.company_id == company.id


def test_self_service_notifications_are_direct_and_hide_annual_plan(db: Session):
    _, company, _, _, user, _ = _seed(db)
    db.add_all([
        Notification(
            company_id=company.id,
            user_id=None,
            type=NotificationType.WARNING,
            title="Geciken yıllık plan faaliyeti",
            message="2026/8: yönetim faaliyeti",
            entity_type="annual_plan",
        ),
        Notification(
            company_id=company.id,
            user_id=user.id,
            type=NotificationType.INFO,
            title="Eğitiminiz devam ediyor",
            message="Atanan eğitiminize devam edebilirsiniz.",
            entity_type="remote_training",
        ),
    ])
    db.flush()

    from app.api.self_service import _notification_summary

    payload = _notification_summary(db, user.id, company.id)
    assert [row["title"] for row in payload["items"]] == ["Eğitiminiz devam ediyor"]
    assert payload["unread"] == 1


def test_self_service_lists_and_downloads_only_own_certificates(db: Session, monkeypatch):
    osgb, company, _other_company, employee, user, _mapping = _seed(db)
    other_employee = Employee(
        company_id=company.id,
        full_name="Ali Kaya",
        job_title="Operatör",
        is_active=True,
    )
    db.add(other_employee)
    db.flush()
    monkeypatch.setattr(settings, "employee_self_service_enabled", True)
    monkeypatch.setattr(settings, "employee_self_service_force_off", False)
    monkeypatch.setattr(settings, "remote_basic_ohs_training_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_training_force_off", False)

    own_training = TrainingSession(
        company_id=company.id,
        title="Temel İSG Eğitimi",
        start_date=date(2026, 3, 10),
        end_date=date(2026, 3, 10),
        hazard_class="Tehlikeli",
        instructor_name="İSG Uzmanı",
        status=TrainingStatus.COMPLETED,
        attendance_verified=True,
        created_by_id=user.id,
    )
    other_training = TrainingSession(
        company_id=company.id,
        title="Yüksekte Çalışma",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 1),
        hazard_class="Tehlikeli",
        instructor_name="İSG Uzmanı",
        status=TrainingStatus.COMPLETED,
        created_by_id=user.id,
    )
    db.add_all([own_training, other_training])
    db.flush()
    db.add_all(
        [
            TrainingParticipant(
                training_id=own_training.id,
                employee_id=employee.id,
                attended=True,
                successful=True,
                certificate_number="EGT-OWN-001",
            ),
            TrainingParticipant(
                training_id=other_training.id,
                employee_id=other_employee.id,
                attended=True,
                successful=True,
                certificate_number="EGT-OTHER-001",
            ),
        ]
    )
    program = RemoteTrainingProgram(
        osgb_id=osgb.id,
        company_id=company.id,
        title="Uzaktan Temel İSG",
        status="published",
        total_duration_seconds=3600,
    )
    db.add(program)
    db.flush()
    assignment = RemoteTrainingAssignment(
        osgb_id=osgb.id,
        company_id=company.id,
        program_id=program.id,
        employee_id=employee.id,
        employee_name_snapshot=employee.full_name,
        workplace_name_snapshot="Merkez İşyeri",
        sgk_registration_number_snapshot="SGK-1",
        nace_code_snapshot="46.83.06",
        nace_description_snapshot="Toptan ticaret",
        hazard_class_snapshot="Tehlikeli",
        status="completed",
        completed_at=datetime(2026, 5, 1, 10, 0, 0),
    )
    pending_assignment = RemoteTrainingAssignment(
        osgb_id=osgb.id,
        company_id=company.id,
        program_id=program.id,
        employee_id=other_employee.id,
        employee_name_snapshot=other_employee.full_name,
        workplace_name_snapshot="Merkez İşyeri",
        sgk_registration_number_snapshot="SGK-1",
        nace_code_snapshot="46.83.06",
        nace_description_snapshot="Toptan ticaret",
        hazard_class_snapshot="Tehlikeli",
        status="in_progress",
    )
    db.add_all([assignment, pending_assignment])
    db.flush()
    _remote_progress(db, assignment)

    payload = build_self_service_payload(
        db,
        user=user,
        company=company,
        employee=employee,
        branch=None,
    )
    certificates = payload["certificates"]["items"]
    assert payload["capabilities"]["can_download_own_certificates"] is True
    assert {row["id"] for row in certificates} == {f"classroom-{own_training.id}", f"remote-{assignment.id}"}
    assert all(row["downloadable"] for row in certificates)
    assert all(row["source_id"] != other_training.id for row in certificates)

    classroom_pdf, classroom_name = build_own_classroom_certificate_pdf(
        db,
        company=company,
        employee=employee,
        training_id=own_training.id,
    )
    assert classroom_pdf.startswith(b"%PDF")
    assert classroom_pdf.count(b"/Type /Page\n") == 1
    assert b"Ali Kaya" not in classroom_pdf
    assert classroom_name.endswith("EGT-OWN-001.pdf")

    with pytest.raises(HTTPException) as other_exc:
        _own_classroom_certificate(db, employee, other_training.id)
    assert other_exc.value.status_code == 403

    remote_pdf, remote_name = build_own_remote_certificate_pdf(
        db,
        employee=employee,
        assignment_id=assignment.id,
    )
    assert remote_pdf.startswith(b"%PDF")
    assert "ROHS-" in remote_name

    with pytest.raises(HTTPException) as pending_exc:
        _own_remote_certificate(db, employee, pending_assignment.id)
    assert pending_exc.value.status_code == 404


@pytest.mark.parametrize("status,verified,attended,future,ready", [
    (TrainingStatus.PLANNED, True, True, False, False),
    (TrainingStatus.COMPLETED, False, True, False, False),
    (TrainingStatus.COMPLETED, True, False, False, False),
    (TrainingStatus.CANCELLED, True, True, False, False),
    (TrainingStatus.COMPLETED, True, True, True, False),
    (TrainingStatus.COMPLETED, True, True, False, True),
])
def test_classroom_document_requires_finished_verified_own_attendance(
    db, certificate_scope, status, verified, attended, future, ready,
):
    _, company, _, employee, user, _ = certificate_scope
    training, participant = _classroom(db, company, employee, user, status=status, attendance_verified=verified)
    participant.attended = attended
    # A success flag must not substitute for attendance.
    participant.successful = True
    if future:
        training.end_date = date.today() + timedelta(days=1)
    db.flush()
    with _client(db, user) as client:
        listing = client.get("/self-service/certificates").json()
        row = listing["items"][0]
        assert row["downloadable"] is ready
        assert bool(row["download_path"]) is ready
        response = client.get(f"/self-service/certificates/classroom/{training.id}.pdf")
        assert response.status_code == (200 if ready else 409)
        if ready:
            assert response.content.startswith(b"%PDF")
            assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("video_complete,passed,snapshot_ready,ready", [
    (False, True, True, False),
    (True, None, True, False),
    (True, False, True, False),
    (True, True, False, False),
    (True, True, True, True),
])
def test_remote_document_checks_video_and_exam_without_mutating_list(
    db, certificate_scope, video_complete, passed, snapshot_ready, ready,
):
    _, company, _, employee, user, _ = certificate_scope
    # Simulate a stale state in both directions: completion must use evidence.
    assignment = _remote(db, company, employee, status="in_progress" if ready else "completed")
    _remote_progress(db, assignment, video_complete=video_complete, passed=passed)
    if not snapshot_ready:
        assignment.sgk_registration_number_snapshot = None
    db.commit()
    previous_state = (assignment.status, assignment.completed_at)
    with _client(db, user) as client:
        row = client.get("/self-service/certificates").json()["items"][0]
        assert row["downloadable"] is ready
        assert bool(row["download_path"]) is ready
        assert (assignment.status, assignment.completed_at) == previous_state
        assert not db.dirty
        assert db.scalar(select(RemoteTrainingCertificate)) is None
        response = client.get(f"/self-service/certificates/remote/{assignment.id}.pdf")
        assert response.status_code == (200 if ready else 409)
        if ready:
            document = db.scalar(select(RemoteTrainingCertificate))
            assert document.employee_id == employee.id
            second = client.get(f"/self-service/certificates/remote/{assignment.id}.pdf")
            assert second.status_code == 200
            assert len(db.scalars(select(RemoteTrainingCertificate)).all()) == 1


@pytest.mark.parametrize("status", ["completed", "revoked", "in_progress"])
def test_issued_remote_documents_remain_available_after_archival(db, certificate_scope, status):
    _, company, _, employee, user, _ = certificate_scope
    assignment = _remote(db, company, employee)
    _remote_progress(db, assignment)
    _, certificate = _own_remote_certificate(db, employee, assignment.id)
    number = certificate.certificate_number
    program = db.get(RemoteTrainingProgram, assignment.program_id)
    program.status = "archived"
    program.title = "Sonradan değişen başlık"
    assignment.status = status
    assignment.sgk_registration_number_snapshot = None
    db.commit()
    with _client(db, user) as client:
        row = client.get("/self-service/certificates").json()["items"][0]
        assert row["downloadable"] is True
        assert row["title"] == certificate.training_name
        assert row["certificate_number"] == number
        assert client.get(row["download_path"]).status_code == 200
        assert assignment.status == status


def test_certificate_routes_isolate_employees_companies_and_pdf_pages(db, certificate_scope):
    _, company, other_company, employee, user, mapping = certificate_scope
    colleague = Employee(company_id=company.id, full_name="Başka Çalışan", is_active=True)
    outsider = Employee(company_id=other_company.id, full_name="Dış Çalışan", is_active=True)
    db.add_all([colleague, outsider])
    db.flush()
    own_training, _ = _classroom(db, company, employee, user)
    db.add(TrainingParticipant(training_id=own_training.id, employee_id=colleague.id, attended=True))
    other_training, _ = _classroom(db, company, colleague, user)
    outside_training, _ = _classroom(db, other_company, outsider, user)
    own_remote = _remote(db, company, employee)
    _remote_progress(db, own_remote)
    other_remote = _remote(db, company, colleague)
    outside_remote = _remote(db, other_company, outsider)
    db.commit()
    with _client(db, user) as client:
        listing = client.get(f"/self-service/certificates?employee_id={colleague.id}&company_id={other_company.id}")
        assert {row["id"] for row in listing.json()["items"]} == {
            f"classroom-{own_training.id}", f"remote-{own_remote.id}",
        }
        for kind, source_id in (("classroom", own_training.id), ("remote", own_remote.id)):
            response = client.get(f"/self-service/certificates/{kind}/{source_id}.pdf")
            assert response.status_code == 200
            pdf = PdfReader(BytesIO(response.content))
            assert len(pdf.pages) == 1
            text = pdf.pages[0].extract_text()
            assert employee.full_name in text
            assert colleague.full_name not in text
            assert outsider.full_name not in text
        for kind, source_id, code in (
            ("classroom", other_training.id, 403), ("classroom", outside_training.id, 404),
            ("remote", other_remote.id, 404), ("remote", outside_remote.id, 404),
        ):
            assert client.get(f"/self-service/certificates/{kind}/{source_id}.pdf").status_code == code
        mapping.is_active = False
        db.commit()
        assert client.get("/self-service/certificates").status_code == 404
        assert client.get(f"/self-service/certificates/remote/{own_remote.id}.pdf").status_code == 404
        assert client.get(f"/self-service/certificates/classroom/{own_training.id}.pdf").status_code == 404


def test_mismatched_historical_certificate_is_never_disclosed(db, certificate_scope):
    _, company, other_company, employee, user, _ = certificate_scope
    assignment = _remote(db, company, employee)
    _remote_progress(db, assignment)
    _, certificate = _own_remote_certificate(db, employee, assignment.id)
    certificate.company_id = other_company.id
    certificate.certificate_number = "MUST-NOT-LEAK"
    db.commit()
    with _client(db, user) as client:
        response = client.get("/self-service/certificates")
        assert response.json()["items"] == []
        assert "MUST-NOT-LEAK" not in response.text
        assert client.get(f"/self-service/certificates/remote/{assignment.id}.pdf").status_code == 409


def test_certificate_history_is_not_truncated_at_100(db, certificate_scope):
    _, company, _, employee, user, _ = certificate_scope
    for _ in range(101):
        _classroom(db, company, employee, user, archived_at=datetime.utcnow())
        _remote(db, company, employee, status="revoked")
    db.commit()
    summary = _certificate_summary(db, company.id, employee.id)
    assert summary["total"] == 202
    assert summary["downloadable"] == 101
    assert sum(row["kind"] == "remote" for row in summary["items"]) == 101
