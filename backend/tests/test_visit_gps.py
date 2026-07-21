"""Faz 2 — ziyaret GPS damgası."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "visit_gps.db"
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


def _seed_field(client: TestClient) -> tuple[str, dict]:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        ServiceVisit,
        User,
        UserRole,
        VisitStatus,
        WorkplaceAssignment,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="GPS OSGB",
            authorization_number="G-001",
            tax_number="5556667778",
            responsible_manager="Yönetici",
            email="gps@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="GPS İşyeri",
            sgk_registry_no="SGK-G01",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Saha Uzman",
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
                email="uzman@test.com",
                full_name="Saha Uzman",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.SAFETY_SPECIALIST,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        visit = ServiceVisit(
            osgb_id=osgb.id,
            company_id=company.id,
            professional_id=pro.id,
            visit_date=date.today(),
            subject="Planlı saha ziyareti",
            duration_minutes=60,
            status=VisitStatus.PLANNED,
        )
        db.add(visit)
        db.commit()
        seed = {"visit_id": visit.id, "company_id": company.id, "osgb_id": osgb.id}

    r = client.post("/api/v1/auth/login", json={"email": "uzman@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed


def test_complete_visit_with_gps(client):
    token, seed = _seed_field(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.patch(
        f"/api/v1/operations/visits/{seed['visit_id']}/complete",
        headers=headers,
        json={"gps_lat": 41.015137, "gps_lng": 28.979530, "gps_accuracy_m": 12.5},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert abs(body["gps_lat"] - 41.015137) < 0.0001
    assert abs(body["gps_lng"] - 28.979530) < 0.0001
    assert body["gps_accuracy_m"] == 12.5
    assert body["gps_captured_at"] is not None


def test_complete_visit_without_gps_still_ok(client):
    token, seed = _seed_field(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.patch(
        f"/api/v1/operations/visits/{seed['visit_id']}/complete",
        headers=headers,
        json={},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"
    assert r.json()["gps_lat"] is None
