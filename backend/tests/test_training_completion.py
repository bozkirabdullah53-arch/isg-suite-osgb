from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import (
    Company,
    Employee,
    TrainingParticipant,
    TrainingSession,
    TrainingStatus,
    User,
    UserRole,
)
from app.models.training_nace import TrainingNaceSnapshot
from app.services import training_pdfs
from app.services.training_completion import (
    completion_preflight,
    finalize_training_results,
    install_training_completion_guard,
)
from app.services.training_nace_classification import resolve_exact_nace

install_training_completion_guard()


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_verified(db: Session):
    company = Company(name="Belge Uygunluk Test", hazard_class="Çok Tehlikeli")
    user = User(
        email="completion@example.com",
        full_name="Belge Test Yöneticisi",
        hashed_password="x",
        role=UserRole.GLOBAL_ADMIN,
    )
    employees = [
        Employee(company=company, full_name="Başarılı Çalışan"),
        Employee(company=company, full_name="Başarısız Çalışan"),
        Employee(company=company, full_name="Katılmayan Çalışan"),
    ]
    db.add_all([company, user, *employees])
    db.flush()
    classification = resolve_exact_nace("nace_30_11_01")
    training = TrainingSession(
        company_id=company.id,
        title="Verified Temel İSG Eğitimi",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        hazard_class=classification.hazard_class,
        sector=classification.catalog_key,
        instructor_name="İSG Uzmanı",
        workplace_physician="İşyeri Hekimi",
        employer_representative="İşveren Vekili",
        evaluation_method="Sınav",
        passing_score=70,
        attendance_verified=False,
        success_verified=False,
        verification_code="VERIFY-COMP-001",
        status=TrainingStatus.PLANNED,
        created_by_id=user.id,
    )
    db.add(training)
    db.flush()
    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(TrainingNaceSnapshot.training_id == training.id)
    )
    if snapshot is None:
        db.add(
            TrainingNaceSnapshot(
                **classification.database_values(
                    training_id=training.id,
                    company_id=company.id,
                    branch_id=None,
                )
            )
        )
    participants = []
    for employee in employees:
        participant = TrainingParticipant(
            training_id=training.id,
            employee_id=employee.id,
            certificate_number=f"EGT-{training.id:06d}-{employee.id:06d}",
        )
        db.add(participant)
        participants.append(participant)
    db.commit()
    db.refresh(training)
    return training, user, employees, participants


def test_preflight_blocks_unfinalized_verified_training(db: Session):
    training, _user, _employees, _participants = _seed_verified(db)
    result = completion_preflight(db, training)
    assert result["strict_applicable"] is True
    assert result["ready_for_certificates"] is False
    assert "Eğitim tamamlandı durumuna alınmamış." in result["training_blockers"]
    assert result["eligible_count"] == 0


def test_finalize_derives_success_and_only_passed_attendee_is_eligible(db: Session):
    training, _user, _employees, participants = _seed_verified(db)
    participants[0].attended = True
    participants[0].score = 85
    participants[1].attended = True
    participants[1].score = 55
    participants[2].attended = False
    db.flush()

    result = finalize_training_results(db, training)
    db.commit()

    assert training.status == TrainingStatus.COMPLETED
    assert training.attendance_verified is True
    assert training.success_verified is True
    assert participants[0].successful is True
    assert participants[1].successful is False
    assert participants[2].successful is False
    assert participants[2].score is None
    assert result["ready_for_certificates"] is True
    assert result["eligible_count"] == 1
    assert result["ineligible_count"] == 2


def test_finalize_fails_closed_when_attendee_score_missing(db: Session):
    training, _user, _employees, participants = _seed_verified(db)
    participants[0].attended = True
    participants[0].score = None
    with pytest.raises(ValueError, match="sınav puanı eksik"):
        finalize_training_results(db, training)


def test_strict_certificate_pdf_blocks_before_finalize(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRAINING_COMPLETION_STRICT", "true")
    training, _user, employees, _participants = _seed_verified(db)
    employee_map = {employee.id: employee for employee in employees}
    with pytest.raises(ValueError, match="Katılım belgesi üretilemez"):
        training_pdfs.build_certificates_pdf(
            company_name="Belge Uygunluk Test",
            training=training,
            employees=employee_map,
        )


def test_strict_certificate_pdf_contains_only_eligible_people(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRAINING_COMPLETION_STRICT", "true")
    training, _user, employees, participants = _seed_verified(db)
    participants[0].attended = True
    participants[0].score = 90
    participants[1].attended = True
    participants[1].score = 40
    participants[2].attended = False
    finalize_training_results(db, training)
    db.commit()

    pdf = training_pdfs.build_certificates_pdf(
        company_name="Belge Uygunluk Test",
        training=training,
        employees={employee.id: employee for employee in employees},
    )
    assert pdf.startswith(b"%PDF")
    # One eligible participant means one certificate page. /Type /Pages is the
    # page tree; /Type /Page is the actual rendered page.
    assert pdf.count(b"/Type /Page") <= 2


def test_legacy_training_keeps_existing_certificate_behavior(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRAINING_COMPLETION_STRICT", "true")
    company = Company(name="Legacy Belge Test", hazard_class="Az Tehlikeli")
    user = User(
        email="legacy-completion@example.com",
        full_name="Legacy Yönetici",
        hashed_password="x",
        role=UserRole.GLOBAL_ADMIN,
    )
    employee = Employee(company=company, full_name="Legacy Çalışan")
    db.add_all([company, user, employee])
    db.flush()
    training = TrainingSession(
        company_id=company.id,
        title="Legacy Eğitim",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 1),
        hazard_class="Az Tehlikeli",
        sector="genel_uretim",
        instructor_name="İSG Uzmanı",
        verification_code="LEGACY-COMP-001",
        created_by_id=user.id,
    )
    db.add(training)
    db.flush()
    db.add(
        TrainingParticipant(
            training_id=training.id,
            employee_id=employee.id,
            certificate_number="LEGACY-001",
        )
    )
    db.commit()
    db.refresh(training)

    preflight = completion_preflight(db, training)
    assert preflight["mode"] == "legacy_compatibility"
    assert preflight["ready_for_certificates"] is True
    pdf = training_pdfs.build_certificates_pdf(
        company_name=company.name,
        training=training,
        employees={employee.id: employee},
    )
    assert pdf.startswith(b"%PDF")
