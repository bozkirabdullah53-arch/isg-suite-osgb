"""0.9.127 — İBYS/KATİP integrations adapter status (stub-clients-v1)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "integrations_status.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    # Ensure no credentials leak from host env into tests by default
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


def _seed_admin(client: TestClient) -> str:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Adapter OSGB",
            authorization_number="YETKI-ADP-1",
            tax_number="1122334455",
            responsible_manager="Adapter Yonetici",
            email="adapter-osgb@test.com",
            phone="02121112233",
            address="Istanbul",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        db.add(
            User(
                email="adapter-admin@test.com",
                full_name="Adapter Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "adapter-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_health_flag_integrations_adapter(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.138"
    assert body["integrations_adapter"] == "stub-clients-v1"
    assert body["integrations_dry_run"] == "log-v1"
    assert body["integration_readiness"] == "checklist-v1"


def test_integrations_status_missing_credentials_stub(client):
    token = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/osgb/integrations/status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status_version"] == "stub-clients-v1"
    assert body["stub"] is True
    assert body["summary"]["ibys_configured"] is False
    assert body["summary"]["katip_configured"] is False
    assert body["adapters"]["ibys"]["status"] == "stub"
    assert body["adapters"]["katip"]["status"] == "stub"
    assert body["adapters"]["ibys"]["configured"] is False
    assert body["adapters"]["katip"]["configured"] is False
    # No secrets in response
    raw = r.text.lower()
    assert "api_key" not in raw
    assert "secret" not in raw


def test_integrations_status_partial_credentials(client, monkeypatch):
    from app.core.config import settings
    from app.services import ibys_client, katip_client

    settings.ibys_api_url = "https://ibys.example.test"
    settings.ibys_api_key = None
    settings.katip_api_url = None
    settings.katip_api_key = "only-key-no-url"
    monkeypatch.setattr(ibys_client, "_last_stub_export_at", None)
    monkeypatch.setattr(katip_client, "_last_stub_export_at", None)

    token = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/osgb/integrations/status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["adapters"]["ibys"]["configured"] is False
    assert body["adapters"]["ibys"]["status"] == "missing_credentials"
    assert body["adapters"]["katip"]["configured"] is False
    assert body["adapters"]["katip"]["status"] == "missing_credentials"
    assert body["summary"]["any_configured"] is False


def test_integrations_status_configured_and_stub_export_timestamp(client, monkeypatch):
    from app.core.config import settings
    from app.services import ibys_client, katip_client

    settings.ibys_api_url = "https://ibys.example.test"
    settings.ibys_api_key = "ibys-test-key"
    settings.katip_api_url = "https://katip.example.test"
    settings.katip_api_key = "katip-test-key"
    monkeypatch.setattr(ibys_client, "_last_stub_export_at", None)
    monkeypatch.setattr(katip_client, "_last_stub_export_at", None)

    payload = ibys_client.export_payload(osgb_id=1, dry_run=True)
    assert payload["status"] == "configured"
    assert payload["dry_run"] is True
    assert ibys_client.last_stub_export_at() is not None

    token = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/osgb/integrations/status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["adapters"]["ibys"]["configured"] is True
    assert body["adapters"]["ibys"]["status"] == "configured"
    assert body["adapters"]["katip"]["configured"] is True
    assert body["adapters"]["katip"]["status"] == "configured"
    assert body["summary"]["ibys_configured"] is True
    assert body["summary"]["katip_configured"] is True
    assert body["adapters"]["ibys"]["last_stub_export_at"] is not None
    assert "ibys-test-key" not in r.text
    assert "katip-test-key" not in r.text


def test_client_validate_config_unit(monkeypatch):
    from app.core.config import settings
    from app.services import ibys_client, katip_client

    settings.ibys_api_url = None
    settings.ibys_api_key = None
    assert ibys_client.status() == "stub"
    assert ibys_client.validate_config()["configured"] is False

    settings.katip_api_url = "https://x"
    settings.katip_api_key = ""
    assert katip_client.status() == "missing_credentials"
