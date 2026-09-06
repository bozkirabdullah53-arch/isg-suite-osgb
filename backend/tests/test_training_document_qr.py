from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def _db():
    from app.core.database import Base
    from app.models import entities  # noqa: F401
    from app.models import remote_training  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _seed_training(db: Session):
    from app.models.entities import (
        Company,
        Employee,
        TrainingParticipant,
        TrainingSession,
        TrainingStatus,
        User,
        UserRole,
    )

    company = Company(name="QR Test Firma", hazard_class="Az Tehlikeli")
    user = User(
        email="qr-test@example.com",
        full_name="QR Test Yöneticisi",
        hashed_password="x",
        role=UserRole.GLOBAL_ADMIN,
    )
    first = Employee(company=company, full_name="İlk Çalışan")
    second = Employee(company=company, full_name="İkinci Çalışan")
    db.add_all([company, user, first, second])
    db.flush()

    training = TrainingSession(
        company_id=company.id,
        title="QR Eğitim Testi",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 1),
        duration_hours=8,
        hazard_class="Az Tehlikeli",
        sector="genel_uretim",
        instructor_name="İSG Uzmanı",
        delivery_method="Yüz yüze",
        training_type="Temel İSG Eğitimi",
        verification_code="TRAINING-QR-001",
        status=TrainingStatus.COMPLETED,
        created_by_id=user.id,
    )
    db.add(training)
    db.flush()
    db.add_all(
        [
            TrainingParticipant(
                training_id=training.id,
                employee_id=first.id,
                certificate_number="EGT-000001-000001",
            ),
            TrainingParticipant(
                training_id=training.id,
                employee_id=second.id,
                certificate_number="EGT-000001-000002",
            ),
        ]
    )
    db.commit()
    db.refresh(training)
    return training, first, second


def test_training_verification_url_is_canonical_and_does_not_embed_private_data(monkeypatch):
    from app.core.config import settings
    from app.services.training_document_qr import training_verification_url

    monkeypatch.setattr(settings, "frontend_origin", "https://www.isgsuite.tr/")
    assert (
        training_verification_url("egt-000001-000001")
        == "https://www.isgsuite.tr/?egitim-dogrula=EGT-000001-000001"
    )
    assert training_verification_url("") is None


def test_draw_training_qr_uses_only_public_verification_url(monkeypatch):
    from app.core.config import settings
    from app.services import training_document_qr

    monkeypatch.setattr(settings, "frontend_origin", "https://www.isgsuite.tr")
    payloads = []

    class FakeCanvas:
        def saveState(self):
            pass

        def setFillColorRGB(self, *_args):
            pass

        def setStrokeColorRGB(self, *_args):
            pass

        def setLineWidth(self, *_args):
            pass

        def roundRect(self, *_args, **_kwargs):
            pass

        def drawImage(self, *_args, **_kwargs):
            pass

        def restoreState(self):
            pass

    monkeypatch.setattr(
        training_document_qr,
        "_qr_image",
        lambda payload: payloads.append(payload) or object(),
    )
    assert training_document_qr.draw_training_qr(
        FakeCanvas(),
        "EGT-000001-000001",
        x=10,
        y=10,
    )
    assert payloads == [
        "https://www.isgsuite.tr/?egitim-dogrula=EGT-000001-000001"
    ]


def test_public_verify_supports_training_and_participant_codes():
    from app.api.trainings import verify_training

    engine = _db()
    with Session(engine) as db:
        _training, first, _second = _seed_training(db)

        training_result = verify_training("training-qr-001", db)
        assert training_result.valid is True
        assert training_result.participant_count == 2
        assert training_result.participant_name is None
        assert len(training_result.participants or []) == 2

        certificate_result = verify_training("egt-000001-000001", db)
        assert certificate_result.valid is True
        assert certificate_result.participant_count == 1
        assert certificate_result.participant_name == first.full_name
        assert certificate_result.certificate_number == "EGT-000001-000001"
        assert certificate_result.participants == [
            {
                "full_name": first.full_name,
                "certificate_number": "EGT-000001-000001",
            }
        ]

        invalid = verify_training("unknown-qr-001", db)
        assert invalid.valid is False


def test_public_verify_supports_issued_remote_certificate_when_pilot_is_disabled(monkeypatch):
    from app.api.training_completion import verify_completed_training
    from app.api.trainings import verify_training
    from app.core.config import settings
    from app.models.remote_training import RemoteTrainingCertificate

    engine = _db()
    with Session(engine) as db:
        _training, first, _second = _seed_training(db)
        remote = RemoteTrainingCertificate(
            company_id=first.company_id,
            program_id=1,
            assignment_id=1,
            employee_id=first.id,
            employee_name_snapshot=first.full_name,
            company_name_snapshot="QR Test Firma",
            training_name="Uzaktan QR Eğitimi",
            training_duration_seconds=5400,
            training_date=date(2026, 9, 2),
            hazard_class_snapshot="Az Tehlikeli",
            instructor_name_snapshot="Uzaktan Eğitici",
            certificate_number="ROHS-TEST-0001",
            verification_code="REMOTE-TEST-CERTIFICATE",
        )
        db.add(remote)
        db.commit()

        # Public verification is for already-issued documents; disabling the
        # creation pilot must not invalidate an existing QR/certificate.
        monkeypatch.setattr(settings, "remote_basic_ohs_training_enabled", False)
        monkeypatch.setattr(settings, "remote_basic_ohs_training_force_off", True)

        result = verify_training(remote.certificate_number, db)
        assert result.valid is True
        assert result.title == "Uzaktan QR Eğitimi"
        assert result.participant_name == first.full_name
        assert result.certificate_number == remote.certificate_number
        assert result.participant_count == 1

        verification_result = verify_training(remote.verification_code, db)
        assert verification_result.valid is True
        assert verification_result.certificate_number == remote.certificate_number

        # The completion router is registered before trainings.py in production.
        prioritized_route_result = verify_completed_training(remote.certificate_number, db)
        assert prioritized_route_result.valid is True
        assert prioritized_route_result.participant_name == first.full_name
        assert prioritized_route_result.certificate_number == remote.certificate_number

        participant_route_result = verify_completed_training("EGT-000001-000001", db)
        assert participant_route_result.valid is True
        assert participant_route_result.participant_name == first.full_name


def test_certificate_pdf_prefers_participant_code_and_falls_back_to_training_code(monkeypatch):
    from app.services import training_pdfs

    monkeypatch.setattr(
        training_pdfs,
        "_draw_certificate_page",
        lambda *_args, **kwargs: captured_codes.append(kwargs["qr_code"]),
    )
    captured_codes = []

    engine = _db()
    with Session(engine) as db:
        training, first, second = _seed_training(db)
        for participant in training.participants:
            if participant.employee_id == second.id:
                participant.certificate_number = None
        db.flush()

        pdf = training_pdfs.build_certificates_pdf(
            company_name="QR Test Firma",
            training=training,
            employees={first.id: first, second.id: second},
        )

    assert pdf.startswith(b"%PDF")
    assert captured_codes == ["EGT-000001-000001", "TRAINING-QR-001"]
