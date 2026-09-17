from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base
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
    RemoteTrainingEmployeeAccess,
    RemoteTrainingProgram,
)
from app.api.self_service import (
    _assert_self_service_user,
    _own_classroom_certificate,
    _own_remote_certificate,
    _resolve_employee_scope,
    build_own_classroom_certificate_pdf,
    build_own_remote_certificate_pdf,
    build_self_service_payload,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


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
