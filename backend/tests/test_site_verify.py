"""İşyeri QR doğrulama — site_verify_code ve ziyaret tamamlama."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.services.site_verify import build_qr_payload


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "site_qr.db"
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


def _seed(client: TestClient) -> tuple[str, dict, str]:
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
    from app.services.site_verify import generate_site_verify_code

    code = generate_site_verify_code()
    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="QR OSGB",
            authorization_number="Q-001",
            tax_number="8887776665",
            responsible_manager="Yönetici",
            email="qr@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="QR İşyeri",
            sgk_registry_no="SGK-Q01",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            site_verify_code=code,
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
        seed = {"visit_id": visit.id, "company_id": company.id, "code": code}

    r = client.post("/api/v1/auth/login", json={"email": "uzman@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed, build_qr_payload(seed["company_id"], code)


def test_complete_visit_requires_valid_qr(client):
    token, seed, payload = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    bad = client.patch(
        f"/api/v1/operations/visits/{seed['visit_id']}/complete",
        headers=headers,
        json={"site_verify_code": "WRONGCODE123"},
    )
    assert bad.status_code == 400

    ok = client.patch(
        f"/api/v1/operations/visits/{seed['visit_id']}/complete",
        headers=headers,
        json={"site_verify_code": payload},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["status"] == "completed"
    assert body["site_verified_at"] is not None


def test_company_site_qr_endpoint(client):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, OsgbOrganization, User, UserRole
    from app.services.site_verify import generate_site_verify_code

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Admin OSGB",
            authorization_number="A-001",
            tax_number="1111111111",
            responsible_manager="Yönetici",
            email="admin@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="QR Admin İşyeri",
            sgk_registry_no="SGK-A01",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            site_verify_code=generate_site_verify_code(),
            is_active=True,
        )
        db.add(company)
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
        cid = company.id

    r = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"})
    token = r.json()["access_token"]
    resp = client.get(f"/api/v1/companies/{cid}/site-qr", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["company_id"] == cid
    assert data["qr_payload"].startswith("ISGSUITE:WP:")
