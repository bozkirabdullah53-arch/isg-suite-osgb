from __future__ import annotations

import base64
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def _engine():
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


def _certificate_for(program, company, employee):
    return SimpleNamespace(
        id=1,
        company_id=company.id,
        program_id=program.id,
        assignment_id=1,
        employee_id=employee.id,
        employee_name_snapshot=employee.full_name,
        company_name_snapshot=company.name,
        workplace_name_snapshot=company.name,
        sgk_registration_number_snapshot="SGK-REMOTE-LOGO-1",
        nace_code_snapshot="46.83.06",
        nace_description_snapshot="Test faaliyet alanı",
        hazard_class_snapshot="Tehlikeli",
        training_name=program.title,
        training_type="Basic Occupational Health and Safety Training",
        training_duration_seconds=3600,
        training_date=date(2026, 9, 14),
        instructor_name_snapshot="İSG Uzmanı Test",
        instructor_qualification_snapshot="A Sınıfı İş Güvenliği Uzmanı",
        workplace_physician_snapshot="İşyeri Hekimi Test",
        employer_representative_snapshot="İşveren Vekili Test",
        examination_score=90,
        certificate_number="ROHS-TEST-0001",
        verification_code="REMOTE-VERIFY-0001",
    )


def test_remote_certificate_uses_current_employee_identity_and_program_logo(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.models.entities import Company, Employee, OsgbOrganization
    from app.models.remote_training import RemoteTrainingProgram
    from app.services import remote_training as service
    from app.services import training_pdfs

    engine = _engine()
    with Session(engine) as db:
        osgb = OsgbOrganization(name="Belge Test OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Belge Test Firma", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        employee = Employee(
            company_id=company.id,
            full_name="Ömer Öztürk",
            national_id_masked="12345678901",
            job_title="Kaynak Operatörü",
            is_active=True,
        )
        program = RemoteTrainingProgram(
            osgb_id=osgb.id,
            company_id=company.id,
            title="Temel İş Sağlığı ve Güvenliği Eğitimi",
            status="published",
        )
        db.add_all([employee, program])
        db.flush()

        upload_root = tmp_path / "uploads"
        logo_rel = Path(str(company.id)) / "remote-training-logos" / str(program.id) / "logo.png"
        logo_abs = upload_root / logo_rel
        logo_abs.parent.mkdir(parents=True, exist_ok=True)
        logo_abs.write_bytes(b"test-logo")
        monkeypatch.setattr(settings, "upload_dir", str(upload_root))
        monkeypatch.setattr(service, "_remote_document_defaults", lambda _db, _company_id: {})

        captured = {}

        def fake_build_certificates_pdf(**kwargs):
            captured.update(kwargs)
            return b"%PDF-test"

        monkeypatch.setattr(training_pdfs, "build_certificates_pdf", fake_build_certificates_pdf)

        result = service.build_certificate_pdf(db, _certificate_for(program, company, employee))

        assert result == b"%PDF-test"
        rendered_employee = captured["employees"][employee.id]
        assert rendered_employee.national_id_masked == "12345678901"
        assert rendered_employee.job_title == "Kaynak Operatörü"
        assert captured["training"].logo_path == logo_rel.as_posix()


def test_remote_program_logo_can_be_uploaded_replaced_and_removed(tmp_path, monkeypatch):
    from app.api.deps import get_current_user
    from app.core.config import settings
    from app.core.database import get_db
    from app.main import app
    from app.models.entities import Company, OsgbOrganization, User, UserRole
    from app.models.remote_training import RemoteTrainingProgram

    engine = _engine()
    with Session(engine) as db:
        osgb = OsgbOrganization(name="Logo API OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Logo API Firma", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        admin = User(
            email="remote-logo-admin@example.com",
            full_name="Remote Logo Admin",
            hashed_password="x",
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            company_id=None,
            is_active=True,
        )
        program = RemoteTrainingProgram(
            osgb_id=osgb.id,
            company_id=company.id,
            title="Logo Test Programı",
            status="published",
        )
        db.add_all([admin, program])
        db.commit()
        admin_id = admin.id
        program_id = program.id
        company_id = company.id

    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(settings, "upload_dir", str(upload_root))
    monkeypatch.setattr(settings, "remote_basic_ohs_training_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_training_force_off", False)
    monkeypatch.setattr(settings, "upload_gateway_enabled", False)

    def override_db():
        with Session(engine) as session:
            yield session

    def override_user():
        with Session(engine) as session:
            return session.get(User, admin_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    client = TestClient(app)
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlKAAAAAASUVORK5CYII="
    )

    try:
        uploaded = client.post(
            f"/api/v1/trainings/remote/programs/{program_id}/logo",
            files={"file": ("firma-logo.png", png, "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        first_rel = uploaded.json()["logo_path"]
        assert first_rel
        assert (upload_root / first_rel).is_file()

        replaced = client.post(
            f"/api/v1/trainings/remote/programs/{program_id}/logo",
            files={"file": ("firma-logo-yeni.png", png, "image/png")},
        )
        assert replaced.status_code == 200, replaced.text
        second_rel = replaced.json()["logo_path"]
        assert second_rel == first_rel
        assert (upload_root / second_rel).is_file()

        removed = client.delete(f"/api/v1/trainings/remote/programs/{program_id}/logo")
        assert removed.status_code == 200, removed.text
        assert removed.json()["logo_path"] is None
        assert not (upload_root / second_rel).exists()

        program_output = client.get(f"/api/v1/trainings/remote/programs/{program_id}")
        assert program_output.status_code == 200, program_output.text
        assert program_output.json()["logo_path"] is None
        assert program_output.json()["company_id"] == company_id
    finally:
        app.dependency_overrides.clear()
