"""Müşteri 360 overview endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "c360.db"
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


def _seed(client: TestClient) -> tuple[str, int]:
    from app.core.database import SessionLocal
    from app.models.entities import Company, OsgbOrganization, User, UserRole
    from app.core.security import get_password_hash

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Test OSGB",
            authorization_number="T-001",
            tax_number="1234567890",
            responsible_manager="Yönetici",
            email="osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Demo İşyeri",
            sgk_registry_no="SGK-001",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
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
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("access_token"), body
    return body["access_token"], cid


def test_company_overview(client):
    token, cid = _seed(client)
    r = client.get(
        f"/api/v1/companies/{cid}/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["company"]["id"] == cid
    assert data["company"]["name"] == "Demo İşyeri"
    assert "counts" in data
    assert "compliance" in data
    assert "assignments" in data


def test_company_get_single(client):
    token, cid = _seed(client)
    r = client.get(
        f"/api/v1/companies/{cid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["sgk_registry_no"] == "SGK-001"
