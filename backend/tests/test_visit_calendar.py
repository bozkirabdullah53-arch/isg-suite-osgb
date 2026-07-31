"""Saha takvimi derinleştirme — takvim, planlı ziyaret, uyarılar."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models.entities import ProfessionalType, ServiceVisit, VisitStatus


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "visit_cal.db"
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


def _seed(client: TestClient) -> tuple[str, dict]:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        IsgProfessional,
        OsgbOrganization,
        User,
        UserRole,
        WorkplaceAssignment,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Takvim OSGB",
            authorization_number="T-002",
            tax_number="9876543210",
            responsible_manager="Yönetici",
            email="takvim@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Takvim İşyeri",
            sgk_registry_no="SGK-T01",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Uzman Demo",
            email="uzman@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            is_active=True,
        )
        db.add(pro)
        db.flush()
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=pro.id,
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                start_date=date.today(),
                status=AssignmentStatus.ACTIVE,
            )
        )
        db.add(
            User(
                email="admin@test.com",
                full_name="OSGB Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()
        seed = {
            "osgb_id": osgb.id,
            "company_id": company.id,
            "professional_id": pro.id,
        }

    r = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("access_token"), body
    return body["access_token"], seed


def test_visit_calendar_month_and_plan(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()
    month = today.strftime("%Y-%m")

    r = client.get(f"/api/v1/operations/visits/calendar?month={month}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["period"] == month
    assert "days" in body
    assert "summary" in body
    assert "alerts" in body
    assert "missing" in body
    assert "missing_coverage" in body["summary"]

    r2 = client.post(
        "/api/v1/operations/visits/plan",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_id": seed["company_id"],
            "professional_id": seed["professional_id"],
            "visit_date": (today + timedelta(days=3)).isoformat(),
            "duration_minutes": 90,
            "notes": "Takvim test planı",
        },
    )
    assert r2.status_code == 200, r2.text
    planned = r2.json()
    assert planned["status"] == VisitStatus.PLANNED.value
    assert planned["company_id"] == seed["company_id"]

    r3 = client.get(f"/api/v1/operations/visits/calendar?month={month}", headers=headers)
    assert r3.status_code == 200
    assert r3.json()["summary"]["planned"] >= 1

    from app.core.database import SessionLocal

    with SessionLocal() as db:
        visit = db.get(ServiceVisit, planned["id"])
        assert visit is not None
        assert visit.status == VisitStatus.PLANNED
