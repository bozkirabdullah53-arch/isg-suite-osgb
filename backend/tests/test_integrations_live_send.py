"""0.9.130 — İBYS/KATİP live-send (live-post-v1)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "integrations_live_send.db"
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
            name="LiveSend OSGB",
            authorization_number="YETKI-LIVE-1",
            tax_number="5566778899",
            responsible_manager="Live Yonetici",
            email="live-osgb@test.com",
            phone="02124445566",
            address="Ankara",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        db.add(
            User(
                email="live-admin@test.com",
                full_name="Live Admin",
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
        json={"email": "live-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return {"token": r.json()["access_token"], "osgb_id": osgb_id}


def test_health_flag_integrations_live_send(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.135"
    assert body["integrations_live_send"] == "live-post-v1"


def test_live_send_missing_credentials_no_network(client, monkeypatch):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    called = {"n": 0}

    def _boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("network must not be called without credentials")

    monkeypatch.setattr("app.services.ibys_client._http_live_post", _boom)
    monkeypatch.setattr("app.services.katip_client._http_live_post", _boom)

    for adapter in ("ibys", "katip"):
        r = client.post(
            f"/api/v1/osgb/integrations/{adapter}/live-send?osgb_id={seed['osgb_id']}",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["adapter"] == adapter
        assert body["ok"] is False
        assert body["status"] == "missing_credentials"
        assert body["log_status"] == "blocked_no_credentials"
        assert body["live_send_version"] == "live-post-v1"
        raw = r.text.lower()
        assert "api_key" not in raw
        assert "secret" not in raw
        assert "http://" not in raw
        assert "https://" not in raw

    assert called["n"] == 0


def test_live_send_configured_mocks_network(client, monkeypatch):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}

    from app.core.config import settings

    settings.ibys_api_url = "https://example.invalid/ibys"
    settings.ibys_api_key = "test-ibys-key-not-for-git"
    settings.katip_api_url = "https://example.invalid/katip"
    settings.katip_api_key = "test-katip-key-not-for-git"

    monkeypatch.setattr(
        "app.services.ibys_client._http_live_post",
        lambda *_a, **_k: {
            "ok": True,
            "status": "live_sent",
            "http_status": 202,
            "elapsed_ms": 18,
        },
    )
    monkeypatch.setattr(
        "app.services.katip_client._http_live_post",
        lambda *_a, **_k: {
            "ok": False,
            "status": "http_error",
            "http_status": 503,
            "elapsed_ms": 9,
        },
    )

    ibys = client.post(
        f"/api/v1/osgb/integrations/ibys/live-send?osgb_id={seed['osgb_id']}",
        headers=headers,
    )
    assert ibys.status_code == 200, ibys.text
    ib = ibys.json()
    assert ib["ok"] is True
    assert ib["status"] == "live_sent"
    assert ib["log_status"] == "live_sent"
    assert ib["http_status"] == 202
    assert "test-ibys-key" not in ibys.text
    assert "example.invalid" not in ibys.text

    katip = client.post(
        f"/api/v1/osgb/integrations/katip/live-send?osgb_id={seed['osgb_id']}",
        headers=headers,
    )
    assert katip.status_code == 200, katip.text
    kt = katip.json()
    assert kt["ok"] is False
    assert kt["status"] == "http_error"
    assert kt["log_status"] == "live_failed"
    assert "test-katip-key" not in katip.text
