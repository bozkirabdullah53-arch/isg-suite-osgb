from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import (
    Company,
    Employee,
    TrainingParticipant,
    TrainingSession,
    User,
    UserRole,
)
from app.models.training_nace import TrainingNaceSnapshot
from app.services import training_pdfs, training_question_bank
from app.services.training_completion import (
    completion_preflight,
    install_training_completion_guard,
)
from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_question_selection_v2 import install_exact_nace_question_selection
from app.services.training_runtime_patches import install_training_runtime_patches

install_training_runtime_patches()
install_exact_nace_question_selection()
install_training_completion_guard()


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed(db: Session):
    company = Company(name="Cutover Test", hazard_class="Çok Tehlikeli")
    user = User(
        email="cutover@example.com",
        full_name="Cutover Yönetici",
        hashed_password="x",
        role=UserRole.GLOBAL_ADMIN,
    )
    employee = Employee(company=company, full_name="Mevcut Çalışan")
    db.add_all([company, user, employee])
    db.flush()
    classification = resolve_exact_nace("nace_30_11_01")
    training = TrainingSession(
        company_id=company.id,
        title="Geçiş Öncesi Eğitim",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        hazard_class=classification.hazard_class,
        sector=classification.catalog_key,
        instructor_name="İSG Uzmanı",
        evaluation_method="Sınav",
        passing_score=70,
        verification_code="CUTOVER-VERIFY-01",
        created_by_id=user.id,
    )
    db.add(training)
    db.flush()
    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(TrainingNaceSnapshot.training_id == training.id)
    )
    if snapshot is None:
        snapshot = TrainingNaceSnapshot(
            **classification.database_values(
                training_id=training.id,
                company_id=company.id,
                branch_id=None,
            )
        )
        db.add(snapshot)
    participant = TrainingParticipant(
        training_id=training.id,
        employee_id=employee.id,
        certificate_number="CUTOVER-CERT-01",
    )
    db.add(participant)
    db.commit()
    db.refresh(training)
    db.refresh(snapshot)
    return training, user, employee, snapshot


def test_future_cutover_preserves_existing_exam_selector(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    training, _user, _employee, snapshot = _seed(db)
    future = snapshot.created_at + timedelta(days=1)
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "true")
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT_AFTER", future.isoformat())

    readiness = training_question_bank.question_bank_readiness(db, training)
    assert readiness["policy"] != "exact-nace-snapshot-foundation-5-plus-work-specific-15-v2"


def test_future_cutover_preserves_existing_certificate_download(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    training, _user, employee, snapshot = _seed(db)
    future = snapshot.created_at + timedelta(days=1)
    monkeypatch.setenv("TRAINING_COMPLETION_STRICT", "true")
    monkeypatch.setenv("TRAINING_COMPLETION_STRICT_AFTER", future.isoformat())

    preflight = completion_preflight(db, training)
    assert preflight["strict_enforced"] is False
    assert preflight["mode"] == "verified_pre_cutover_compatibility"
    pdf = training_pdfs.build_certificates_pdf(
        company_name="Cutover Test",
        training=training,
        employees={employee.id: employee},
    )
    assert pdf.startswith(b"%PDF")


def test_past_cutover_enforces_new_verified_workflows(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    training, _user, _employee, snapshot = _seed(db)
    past = snapshot.created_at - timedelta(seconds=1)
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "true")
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT_AFTER", past.isoformat())
    monkeypatch.setenv("TRAINING_COMPLETION_STRICT", "true")
    monkeypatch.setenv("TRAINING_COMPLETION_STRICT_AFTER", past.isoformat())

    readiness = training_question_bank.question_bank_readiness(db, training)
    assert readiness["policy"] == "exact-nace-snapshot-foundation-5-plus-work-specific-15-v2"
    preflight = completion_preflight(db, training)
    assert preflight["strict_enforced"] is True
    assert preflight["ready_for_certificates"] is False
