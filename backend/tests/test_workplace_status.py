"""İşyeri Durum Merkezi: tenant izolasyonu, mahremiyet ve rapor smoke testleri."""
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "workplace-status.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed() -> dict:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        Employee,
        HealthFitnessStatus,
        HealthRecord,
        HealthRecordType,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        User,
        UserRole,
        WorkplaceAssignment,
    )

    password = "TestPass123!"
    with SessionLocal() as db:
        osgb_1 = OsgbOrganization(name="Birinci OSGB", authorization_number="OSGB-1", is_active=True)
        osgb_2 = OsgbOrganization(name="İkinci OSGB", authorization_number="OSGB-2", is_active=True)
        db.add_all([osgb_1, osgb_2])
        db.flush()
        company_1 = Company(name="Yetkili İşyeri", osgb_id=osgb_1.id, is_active=True, hazard_class="Tehlikeli")
        company_2 = Company(name="Yabancı İşyeri", osgb_id=osgb_2.id, is_active=True, hazard_class="Tehlikeli")
        db.add_all([company_1, company_2])
        db.flush()

        admin = User(
            email="admin@birinci.example.com", full_name="Birinci OSGB Admin", hashed_password=get_password_hash(password),
            role=UserRole.COMPANY_ADMIN, osgb_id=osgb_1.id, is_active=True,
        )
        employer = User(
            email="employer@birinci.example.com", full_name="İşveren", hashed_password=get_password_hash(password),
            role=UserRole.READ_ONLY, company_id=company_1.id, osgb_id=osgb_1.id, is_active=True,
        )
        specialist = User(
            email="uzman@birinci.example.com", full_name="Atanmış Uzman", hashed_password=get_password_hash(password),
            role=UserRole.SAFETY_SPECIALIST, osgb_id=osgb_1.id, is_active=True,
        )
        db.add_all([admin, employer, specialist])
        db.flush()
        professional = IsgProfessional(
            osgb_id=osgb_1.id,
            full_name="Atanmış Uzman",
            email="uzman@birinci.example.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="A-100",
            is_active=True,
        )
        db.add(professional)
        db.flush()
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb_1.id,
                company_id=company_1.id,
                professional_id=professional.id,
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                start_date=date.today(),
                status=AssignmentStatus.ACTIVE,
            )
        )
        employee = Employee(company_id=company_1.id, full_name="Gizli Çalışan", is_active=True)
        db.add(employee)
        db.flush()
        db.add(
            HealthRecord(
                company_id=company_1.id,
                employee_id=employee.id,
                record_type=HealthRecordType.PERIODIC_EXAM,
                examination_date=date.today() - timedelta(days=300),
                next_examination_date=date.today() - timedelta(days=1),
                fitness_status=HealthFitnessStatus.CONDITIONAL,
                summary="GİZLİ_TANI_METNİ",
                confidential_note="GİZLİ_HEKİM_NOTU",
                restrictions="GİZLİ_KISITLAMA",
                created_by_id=admin.id,
            )
        )
        db.commit()
        return {
            "password": password,
            "company_1": company_1.id,
            "company_2": company_2.id,
            "users": [admin.email, employer.email, specialist.email],
        }


def _token(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_status_isolated_for_admin_employer_and_assigned_specialist(client):
    seed = _seed()
    for email in seed["users"]:
        headers = {"Authorization": f"Bearer {_token(client, email, seed['password'])}"}
        own = client.get(f"/api/v1/companies/{seed['company_1']}/status", headers=headers)
        assert own.status_code == 200, (email, own.text)
        assert own.headers["cache-control"] == "no-store"
        assert own.json()["company"]["id"] == seed["company_1"]
        if email != seed["users"][0]:
            assert "finance" not in own.json()
            assert "contracts" not in own.json()

        foreign = client.get(f"/api/v1/companies/{seed['company_2']}/status", headers=headers)
        assert foreign.status_code == 403, (email, foreign.text)


def test_status_never_exposes_sensitive_medical_fields_or_ibys_ready_claim(client):
    seed = _seed()
    headers = {"Authorization": f"Bearer {_token(client, seed['users'][0], seed['password'])}"}
    response = client.get(f"/api/v1/companies/{seed['company_1']}/status", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    serialized = response.text
    assert "GİZLİ_TANI_METNİ" not in serialized
    assert "GİZLİ_HEKİM_NOTU" not in serialized
    assert "GİZLİ_KISITLAMA" not in serialized
    assert "unfit" not in payload["health"]
    assert payload["status_center"]["privacy"] == {
        "medical_data_mode": "aggregate_only",
        "sensitive_fields_exposed": False,
    }
    ibys = payload["status_center"]["ibys_validation"]
    assert ibys["officially_verified"] is False
    assert ibys["readiness_claim"] is False
    assert ibys["status"] == "pending_official_validation"


def test_one_click_pdf_and_excel_reports_are_valid_and_scoped(client):
    seed = _seed()
    headers = {"Authorization": f"Bearer {_token(client, seed['users'][0], seed['password'])}"}
    pdf = client.get(f"/api/v1/companies/{seed['company_1']}/status/report.pdf", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.headers["cache-control"] == "no-store"

    excel = client.get(f"/api/v1/companies/{seed['company_1']}/status/report.xlsx", headers=headers)
    assert excel.status_code == 200, excel.text
    assert excel.content.startswith(b"PK")
    assert "spreadsheetml" in excel.headers["content-type"]
    assert excel.headers["cache-control"] == "no-store"

    foreign = client.get(f"/api/v1/companies/{seed['company_2']}/status/report.pdf", headers=headers)
    assert foreign.status_code == 403


def test_forgot_password_keeps_neutral_response_and_does_not_crash(client):
    seed = _seed()
    response = client.post("/api/v1/auth/forgot-password", json={"email": seed["users"][1]})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "message": "Eğer hesap varsa sıfırlama bağlantısı e-posta ile gönderildi."
    }

    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "unknown@example.com"})
    assert unknown.status_code == 200
    assert unknown.json() == response.json()


def test_report_exports_neutralize_excel_formula_and_escape_pdf_markup():
    from app.services.workplace_status_reports import (
        build_workplace_status_excel,
        build_workplace_status_pdf,
    )

    payload = {
        "company": {"name": "<b>Deneme & İşyeri</b>", "sgk_registry_no": "=1+1"},
        "status_center": {
            "overall_label": "İzleme",
            "completion_pct": 50,
            "generated_at": "2026-08-04T00:00:00Z",
            "items": [{
                "code": "risk",
                "title": "=HYPERLINK(\"https://evil.invalid\")",
                "status_label": "Eksik",
                "detail": "<script>değil</script> & güvenli",
                "responsible_role": "+Sorumlu",
                "source": "risk_assessments",
                "module": "risk",
                "critical": True,
            }],
            "deadlines": [],
        },
    }
    excel = build_workplace_status_excel(payload)
    workbook = load_workbook(BytesIO(excel), data_only=False)
    assert workbook["Durum Özeti"]["B2"].value == "'=1+1"
    assert workbook["Süreç Durumları"]["B2"].value.startswith("'=")
    assert workbook["Süreç Durumları"]["E2"].value.startswith("'+")

    pdf = build_workplace_status_pdf(payload)
    assert pdf.startswith(b"%PDF")
