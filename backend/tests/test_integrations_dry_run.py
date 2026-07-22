"""0.9.126 — İBYS/KATİP dry-run export log (log-v1)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "integrations_dry_run.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.delenv("IBYS_API_URL", raising=False)
    monkeypatch.delenv("IBYS_API_KEY", raising=False)
    monkeypatch.delenv("KATIP_API_URL", raising=False)
    monkeypatch.delenv("KATIP_API_KEY", raising=False)
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"
    settings.ibys_api_url = None
    settings.ibys_api_key = None
    settings.katip_api_url = None
    settings.katip_api_key = None

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed(client: TestClient) -> dict:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, Employee, OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="DryRun OSGB",
            authorization_number="YETKI-DRY-1",
            tax_number="5566778899",
            responsible_manager="DryRun Yonetici",
            email="dryrun-osgb@test.com",
            phone="02129998877",
            address="Ankara",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="DryRun Firma",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Az Tehlikeli",
        )
        db.add(company)
        db.flush()
        db.add(
            Employee(
                company_id=company.id,
                full_name="DryRun Calisan",
                national_id_masked="*******1110",
                is_active=True,
            )
        )
        db.add(
            User(
                email="dryrun-admin@test.com",
                full_name="DryRun Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()
        osgb_id = osgb.id

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "dryrun-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return {"token": r.json()["access_token"], "osgb_id": osgb_id}


def test_health_flag_integrations_dry_run(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.126"
    assert body["integrations_dry_run"] == "log-v1"
    assert body["integrations_adapter"] == "stub-clients-v1"


def test_dry_run_ibys_logs_and_status(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    r = client.post(
        f"/api/v1/osgb/integrations/ibys/dry-run?osgb_id={seed['osgb_id']}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["adapter"] == "ibys"
    assert body["status"] == "dry_run"
    assert body["dry_run_version"] == "log-v1"
    assert body["record_count"] >= 2  # 1 company + 1 employee
    assert body["who"] == "dryrun-admin@test.com"
    assert body["payload"]["dry_run"] is True
    raw = r.text.lower()
    assert "api_key" not in raw
    assert "secret" not in raw

    st = client.get(
        f"/api/v1/osgb/integrations/status?osgb_id={seed['osgb_id']}",
        headers=headers,
    )
    assert st.status_code == 200, st.text
    status = st.json()
    assert status["summary"]["dry_run_count"] >= 1
    assert len(status["last_dry_runs"]) >= 1
    last = status["last_dry_runs"][0]
    assert last["adapter"] == "ibys"
    assert last["status"] == "dry_run"
    assert last["who"] == "dryrun-admin@test.com"
    assert last["record_count"] >= 2


def test_dry_run_katip_and_invalid_adapter(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    r = client.post(
        f"/api/v1/osgb/integrations/katip/dry-run?osgb_id={seed['osgb_id']}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["adapter"] == "katip"
    assert body["status"] == "dry_run"
    assert body["record_count"] >= 0

    bad = client.post("/api/v1/osgb/integrations/foo/dry-run", headers=headers)
    assert bad.status_code == 400
