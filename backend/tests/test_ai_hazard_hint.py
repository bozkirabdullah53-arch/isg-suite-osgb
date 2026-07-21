"""0.9.117 — Tehlike önerisi (keyword-v1) MVP."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.ai_hazard_hint import HINT_ENGINE, suggest_hazard_from_text


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "hazard_hint.db"
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


def _login_specialist(client: TestClient) -> str:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Hint OSGB",
            authorization_number="YETKI-HINT-1",
            tax_number="1122334455",
            responsible_manager="Yonetici",
            email="hint-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(name="Hint Firma", osgb_id=osgb.id, is_active=True, hazard_class="Tehlikeli")
        db.add(company)
        db.flush()
        db.add(
            User(
                email="hint-uzman@test.com",
                full_name="Hint Uzman",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.SAFETY_SPECIALIST,
                osgb_id=osgb.id,
                company_id=company.id,
                is_active=True,
            )
        )
        db.commit()

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "hint-uzman@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_suggest_electric_and_height():
    el = suggest_hazard_from_text("Elektrik panosunda açık kablo ve topraklama eksik")
    assert el["matched"] is True
    assert el["suggested_category"] == "Elektrik Riskleri"
    assert el["probability_hint"] >= 3
    assert el["engine"] == HINT_ENGINE

    hi = suggest_hazard_from_text("Çatıda iskele kurulumu, yüksekte çalışma, düşme riski")
    assert hi["matched"] is True
    assert hi["suggested_category"] == "Yüksekte Çalışma Riskleri"


def test_suggest_empty():
    empty = suggest_hazard_from_text("ab")
    assert empty["matched"] is False


def test_health_flag_ai_hazard_hint(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.120"
    assert body["ai_hazard_hint"] == "keyword-v1"


def test_hazard_hint_endpoint(client):
    token = _login_specialist(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/v1/risks/hazard-hint",
        headers=headers,
        json={
            "activity": "Kaynak işi",
            "risk_definition": "Yanıcı gaz tüpleri yanında kıvılcım ve yangın riski",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "keyword-v1"
    assert body["matched"] is True
    assert body["suggested_category"] == "Yangın ve Patlama Riskleri"
    assert body.get("category_id") is not None
    assert body["probability_hint"] >= 3
