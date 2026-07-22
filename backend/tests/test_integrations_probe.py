"""0.9.127 — İBYS/KATİP safe connection probe (live-check-v1)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "integrations_probe.db"
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
    from app.models.entities import OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Probe OSGB",
            authorization_number="YETKI-PROBE-1",
            tax_number="1122334455",
            responsible_manager="Probe Yonetici",
            email="probe-osgb@test.com",
            phone="02121112233",
            address="Istanbul",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        db.add(
            User(
                email="probe-admin@test.com",
                full_name="Probe Admin",
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
        json={"email": "probe-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return {"token": r.json()["access_token"], "osgb_id": osgb_id}


def test_health_flag_integrations_probe(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.142"
    assert body["integrations_probe"] == "live-check-v1"
    assert body["integrations_dry_run"] == "log-v1"


def test_probe_missing_credentials_no_network(client, monkeypatch):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}

    called = {"n": 0}

    def _boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("network must not be called without credentials")

    monkeypatch.setattr("app.services.ibys_client._http_probe", _boom)
    monkeypatch.setattr("app.services.katip_client._http_probe", _boom)

    for adapter in ("ibys", "katip"):
        r = client.post(f"/api/v1/osgb/integrations/{adapter}/probe", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["adapter"] == adapter
        assert body["ok"] is False
        assert body["status"] == "missing_credentials"
        assert body["probe_version"] == "live-check-v1"
        raw = r.text.lower()
        assert "api_key" not in raw
        assert "secret" not in raw
        assert "http://" not in raw
        assert "https://" not in raw

    assert called["n"] == 0

    bad = client.post("/api/v1/osgb/integrations/foo/probe", headers=headers)
    assert bad.status_code == 400


def test_probe_configured_mocks_network(client, monkeypatch):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}

    from app.core.config import settings

    settings.ibys_api_url = "https://example.invalid/ibys"
    settings.ibys_api_key = "test-ibys-key-not-for-git"
    settings.katip_api_url = "https://example.invalid/katip"
    settings.katip_api_key = "test-katip-key-not-for-git"

    monkeypatch.setattr(
        "app.services.ibys_client._http_probe",
        lambda _url: {
            "ok": True,
            "status": "reachable",
            "http_status": 200,
            "elapsed_ms": 12,
        },
    )
    monkeypatch.setattr(
        "app.services.katip_client._http_probe",
        lambda _url: {
            "ok": False,
            "status": "unreachable",
            "http_status": None,
            "elapsed_ms": 5,
        },
    )

    ibys = client.post("/api/v1/osgb/integrations/ibys/probe", headers=headers)
    assert ibys.status_code == 200, ibys.text
    ib = ibys.json()
    assert ib["ok"] is True
    assert ib["status"] == "reachable"
    assert ib["http_status"] == 200
    assert "test-ibys-key" not in ibys.text
    assert "example.invalid" not in ibys.text

    katip = client.post("/api/v1/osgb/integrations/katip/probe", headers=headers)
    assert katip.status_code == 200, katip.text
    kt = katip.json()
    assert kt["ok"] is False
    assert kt["status"] == "unreachable"
    assert "test-katip-key" not in katip.text
