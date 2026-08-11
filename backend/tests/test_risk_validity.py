"""Risk değerlendirmesi geçerlilik/yenileme takibi ve rapor künyesi.

Yönetmelik md.12: az tehlikeli 6, tehlikeli 4, çok tehlikeli 2 yılda bir yenileme.
Yönetmelik md.15: dokümanda yöntem ve değerlendirmeyi yapan ekip yer alır.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.services.risk_validity import (
    METHOD_LABEL,
    add_years,
    build_validity,
    document_meta_rows,
    renewal_years,
)


def test_renewal_years_by_hazard_class():
    assert renewal_years("Az Tehlikeli") == 6
    assert renewal_years("Tehlikeli") == 4
    assert renewal_years("Çok Tehlikeli") == 2
    assert renewal_years("çok tehlikeli") == 2
    assert renewal_years(None) is None
    assert renewal_years("Bilinmiyor") is None


def test_add_years_handles_leap_day():
    assert add_years(date(2024, 2, 29), 2) == date(2026, 2, 28)
    assert add_years(date(2023, 5, 10), 4) == date(2027, 5, 10)


def test_validity_ok_due_soon_and_expired():
    today = date(2026, 7, 28)

    ok = build_validity(
        hazard_class="Tehlikeli", assessment_date=date(2025, 1, 1), today=today
    )
    assert ok["status"] == "ok"
    assert ok["valid_until"] == "2029-01-01"
    assert ok["renewal_years"] == 4

    soon = build_validity(
        hazard_class="Çok Tehlikeli", assessment_date=date(2024, 9, 1), today=today
    )
    assert soon["status"] == "due_soon"
    assert 0 <= soon["days_left"] <= 90

    expired = build_validity(
        hazard_class="Az Tehlikeli", assessment_date=date(2019, 1, 1), today=today
    )
    assert expired["status"] == "expired"
    assert expired["days_left"] < 0
    assert "doldu" in expired["message"]


def test_validity_unknown_states():
    no_class = build_validity(hazard_class=None, assessment_date=date(2025, 1, 1))
    assert no_class["status"] == "unknown"
    assert no_class["renewal_years"] is None

    no_date = build_validity(hazard_class="Tehlikeli", assessment_date=None)
    assert no_date["status"] == "unknown"
    assert no_date["assessment_date_source"] == "missing"


def test_validity_falls_back_to_first_risk_record():
    body = build_validity(
        hazard_class="Tehlikeli",
        assessment_date=None,
        fallback_date=date(2025, 3, 1),
        today=date(2026, 7, 28),
    )
    assert body["assessment_date_source"] == "estimated"
    assert body["valid_until"] == "2029-03-01"
    assert "tahmin" in body["message"]


def test_document_meta_rows_carry_method_and_team():
    rows = dict(
        document_meta_rows(
            validity=build_validity(
                hazard_class="Tehlikeli", assessment_date=date(2025, 1, 1), today=date(2026, 1, 1)
            ),
            prepared_by="Uzman Kisi",
            workplace_physician="Hekim Kisi",
            employer_representative="Isveren Vekili",
            employee_representative="Calisan Temsilcisi",
            support_staff="Destek Elemani",
        )
    )
    assert rows["Kullanılan Yöntem"] == METHOD_LABEL
    assert rows["Değerlendirme Tarihi"] == "01.01.2025"
    assert rows["Geçerlilik / Yenileme Tarihi"] == "01.01.2029"
    assert rows["Yenileme Periyodu"].startswith("4 yıl")
    assert rows["Çalışan Temsilcisi"] == "Calisan Temsilcisi"
    assert rows["Destek Elemanı"] == "Destek Elemani"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "risk_validity.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"
    settings.upload_dir = str(tmp_path / "uploads")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.core.database as dbmod
    import app.models.entities as ent

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed(client: TestClient) -> dict:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        User,
        UserRole,
        WorkplaceAssignment,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Risk OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(
            name="Risk Firma",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            authorized_person="Isveren Vekili",
            is_active=True,
        )
        db.add(company)
        db.flush()
        specialist = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Uzman Kisi",
            email="risk-uzman@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            is_active=True,
        )
        physician = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Hekim Kisi",
            email="risk-hekim@test.com",
            professional_type=ProfessionalType.WORKPLACE_PHYSICIAN,
            is_active=True,
        )
        db.add_all([specialist, physician])
        db.flush()
        for pro in (specialist, physician):
            db.add(
                WorkplaceAssignment(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    professional_id=pro.id,
                    professional_type=pro.professional_type,
                    start_date=date.today(),
                    status=AssignmentStatus.ACTIVE,
                )
            )
        db.add_all(
            [
                User(
                    email="risk-uzman@test.com",
                    full_name="Uzman Kisi",
                    hashed_password=get_password_hash("UzmanPass123!"),
                    role=UserRole.SAFETY_SPECIALIST,
                    osgb_id=osgb.id,
                    company_id=company.id,
                    is_active=True,
                ),
                User(
                    email="risk-osgb@test.com",
                    full_name="OSGB Yonetici",
                    hashed_password=get_password_hash("OsgbPass123!"),
                    role=UserRole.COMPANY_ADMIN,
                    osgb_id=osgb.id,
                    is_active=True,
                ),
            ]
        )
        db.commit()
        return {"company_id": company.id, "osgb_id": osgb.id}


def _headers(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_validity_endpoint_reports_missing_date_then_tracks_it(client):
    seed = _seed(client)
    headers = _headers(client, "risk-uzman@test.com", "UzmanPass123!")
    cid = seed["company_id"]

    first = client.get(f"/api/v1/risks/validity?company_id={cid}", headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["renewal_years"] == 4
    assert body["status"] == "unknown"
    assert body["team"]["workplace_physician"] == "Hekim Kisi"
    assert body["team"]["employer_representative"] == "Isveren Vekili"

    saved = client.put(
        "/api/v1/risks/assessment-info",
        headers=headers,
        json={
            "company_id": cid,
            "assessment_date": (date.today() - timedelta(days=30)).isoformat(),
            "employee_representative": "Calisan Temsilcisi",
            "support_staff": "Destek Elemani",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "ok"
    assert saved.json()["assessment_date_source"] == "recorded"
    assert saved.json()["team"]["employee_representative"] == "Calisan Temsilcisi"

    stats = client.get(f"/api/v1/risks/stats?company_id={cid}", headers=headers)
    assert stats.status_code == 200, stats.text
    assert stats.json()["validity"]["status"] == "ok"


def test_nace_roadmap_endpoint_uses_assigned_company_and_fails_closed(client):
    seed = _seed(client)
    cid = seed["company_id"]
    from app.core.database import SessionLocal
    from app.models.entities import Company

    with SessionLocal() as db:
        company = db.get(Company, cid)
        company.nace_code = "46.83.06"
        db.commit()

    headers = _headers(client, "risk-uzman@test.com", "UzmanPass123!")
    response = client.get(f"/api/v1/risks/nace-roadmap?company_id={cid}", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "verified"
    assert body["identity"]["code"] == "46.83.06"
    assert body["coverage"]["risk_records"] == 0

    with SessionLocal() as db:
        company = db.get(Company, cid)
        company.nace_code = None
        company.sgk_registry_no = "22410010110202140161220000"
        db.commit()
    sgk_scope = client.get(f"/api/v1/risks/nace-roadmap?company_id={cid}", headers=headers)
    assert sgk_scope.status_code == 200, sgk_scope.text
    assert sgk_scope.json()["entered_nace_code"] == "24.10"
    assert sgk_scope.json()["nace_source"] == "sgk_work_code"
    assert sgk_scope.json()["status"] == "review_required"

    with SessionLocal() as db:
        company = db.get(Company, cid)
        company.nace_code = "99.99.99"
        db.commit()
    invalid = client.get(f"/api/v1/risks/nace-roadmap?company_id={cid}", headers=headers)
    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["status"] == "invalid"
    assert invalid.json()["identity"] is None


def test_nace_roadmap_endpoint_keeps_assignment_boundary(client):
    seed = _seed(client)
    headers = _headers(client, "risk-uzman@test.com", "UzmanPass123!")
    response = client.get("/api/v1/risks/nace-roadmap?company_id=999999", headers=headers)
    assert response.status_code == 403


def test_expired_assessment_is_reported(client):
    seed = _seed(client)
    headers = _headers(client, "risk-uzman@test.com", "UzmanPass123!")
    cid = seed["company_id"]

    client.put(
        "/api/v1/risks/assessment-info",
        headers=headers,
        json={"company_id": cid, "assessment_date": (date.today() - timedelta(days=5 * 365)).isoformat()},
    )
    body = client.get(f"/api/v1/risks/validity?company_id={cid}", headers=headers).json()
    assert body["status"] == "expired"
    assert "zorunlu" in body["message"]


def test_future_assessment_date_rejected(client):
    seed = _seed(client)
    headers = _headers(client, "risk-uzman@test.com", "UzmanPass123!")
    r = client.put(
        "/api/v1/risks/assessment-info",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "assessment_date": (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    assert r.status_code == 422


def _seed_one_risk(company_id: int) -> None:
    from app.core.database import SessionLocal
    from app.models.entities import Hazard, HazardCategory, RiskAssessment, User
    from app.services.risk_scoring import evaluate
    from sqlalchemy import select as sa_select

    with SessionLocal() as db:
        author = db.scalar(sa_select(User).where(User.email == "risk-uzman@test.com"))
        cat = HazardCategory(name="Mekanik", icon="gear", sort_order=1)
        db.add(cat)
        db.flush()
        hazard = Hazard(category_id=cat.id, code="MEK-001", name="Dönen aksam", is_active=True)
        db.add(hazard)
        db.flush()
        scored = evaluate(4, 4)
        db.add(
            RiskAssessment(
                risk_code="RSK-VAL-1",
                company_id=company_id,
                hazard_id=hazard.id,
                department_name="Uretim",
                activity="Torna",
                risk_definition="Koruyucusuz donen aksam",
                probability=4,
                severity=4,
                risk_score=scored["risk_score"],
                risk_level=scored["risk_level"],
                term_days=scored["term_days"],
                status="Açık",
                created_by_id=author.id,
            )
        )
        db.commit()


def test_reports_render_with_document_meta(client):
    """Rapor uçları künye eklendikten sonra da üretilebilmeli (regresyon kalkanı)."""
    seed = _seed(client)
    headers = _headers(client, "risk-uzman@test.com", "UzmanPass123!")
    cid = seed["company_id"]
    _seed_one_risk(cid)
    client.put(
        "/api/v1/risks/assessment-info",
        headers=headers,
        json={
            "company_id": cid,
            "assessment_date": date.today().isoformat(),
            "employee_representative": "Calisan Temsilcisi",
        },
    )

    pdf = client.get(f"/api/v1/risks/report.pdf?company_id={cid}", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.content[:4] == b"%PDF"

    xlsx = client.get(f"/api/v1/risks/report.xlsx?company_id={cid}", headers=headers)
    assert xlsx.status_code == 200, xlsx.text
    assert xlsx.content[:2] == b"PK"


def test_osgb_admin_cannot_write_assessment_info(client):
    seed = _seed(client)
    headers = _headers(client, "risk-osgb@test.com", "OsgbPass123!")
    r = client.put(
        "/api/v1/risks/assessment-info",
        headers=headers,
        json={"company_id": seed["company_id"], "assessment_date": date.today().isoformat()},
    )
    assert r.status_code == 403
