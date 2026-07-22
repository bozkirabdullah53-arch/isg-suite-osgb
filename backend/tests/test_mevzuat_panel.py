"""0.9.121 — OSGB mevzuat mini panel (highlights-v1)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.mevzuat_panel import PANEL_ENGINE, build_mevzuat_panel


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "mevzuat_panel.db"
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


def _login_admin(client: TestClient) -> str:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Mevzuat OSGB",
            authorization_number="YETKI-MEV-1",
            tax_number="5566778899",
            responsible_manager="Yonetici",
            email="mevzuat-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        db.add(
            User(
                email="mevzuat-admin@test.com",
                full_name="Mevzuat Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "mevzuat-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_build_panel_basics():
    body = build_mevzuat_panel()
    assert body["engine"] == PANEL_ENGINE
    assert body["last_reviewed"]
    assert len(body["highlights"]) >= 5
    assert body["catalog_total"] > 10
    assert any(c["name"] == "Elektrik Riskleri" for c in body["categories"])


def test_build_panel_category_and_search():
    cat = build_mevzuat_panel(category="Elektrik Riskleri")
    assert cat["selected_category"] == "Elektrik Riskleri"
    assert any("Elektrik" in x["name"] for x in cat["catalog"])

    q = build_mevzuat_panel(q="eğitim")
    assert q["query"] == "eğitim"
    assert any("eğitim" in h["title"].casefold() or "eğitim" in h["summary"].casefold() for h in q["highlights"])


def test_health_flag_mevzuat_panel(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.140"
    assert body["mevzuat_panel"] == "highlights-v1"
    assert body["ai_hazard_hint"] == "keyword-v2"


def test_mevzuat_panel_endpoint(client):
    token = _login_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/osgb/mevzuat-panel", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "highlights-v1"
    assert len(body["highlights"]) >= 5

    r2 = client.get(
        "/api/v1/osgb/mevzuat-panel",
        headers=headers,
        params={"category": "Kimyasal Riskler"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["selected_category"] == "Kimyasal Riskler"
