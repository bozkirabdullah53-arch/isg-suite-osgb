"""P1-12 legal acceptance + P1-03 company assert tests."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.tenant_context import (
    assert_company_access,
    bind_user_tenant,
    clear_tenant,
    set_tenant,
    tenant_from_user,
)
from app.models.entities import User, UserRole


@pytest.fixture(autouse=True)
def _clear_tenant():
    clear_tenant()
    yield
    clear_tenant()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "legal.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _login(client: TestClient) -> str:
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        u = User(
            email="legal@test.com",
            full_name="Legal User",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.READ_ONLY,
            is_active=True,
        )
        db.add(u)
        db.commit()

    r = client.post("/api/v1/auth/login", json={"email": "legal@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_legal_documents_and_accept_idempotent(client):
    token = _login(client)
    h = {"Authorization": f"Bearer {token}"}

    docs = client.get("/api/v1/legal/documents", headers=h)
    assert docs.status_code == 200
    body = docs.json()
    assert len(body) >= 3
    keys = {d["key"] for d in body}
    assert "privacy_notice" in keys
    assert "explicit_consent_health" in keys
    assert all(d["accepted"] is False for d in body)

    acc = client.post(
        "/api/v1/legal/accept",
        headers=h,
        json={"document_key": "privacy_notice"},
    )
    assert acc.status_code == 200, acc.text
    assert acc.json()["document_key"] == "privacy_notice"
    assert acc.json()["legal_basis"] == "kvkk_art_10"
    first_id = acc.json()["id"]

    # Aynı sürüm tekrar → aynı kayıt
    acc2 = client.post(
        "/api/v1/legal/accept",
        headers=h,
        json={"document_key": "privacy_notice"},
    )
    assert acc2.status_code == 200
    assert acc2.json()["id"] == first_id

    docs2 = client.get("/api/v1/legal/documents", headers=h).json()
    privacy = next(d for d in docs2 if d["key"] == "privacy_notice")
    assert privacy["accepted"] is True

    me = client.get("/api/v1/legal/me", headers=h)
    assert me.status_code == 200
    assert len(me.json()) == 1


def test_legal_stale_version_rejected(client):
    token = _login(client)
    h = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/v1/legal/accept",
        headers=h,
        json={"document_key": "terms_of_use", "document_version": "1999-01-01"},
    )
    assert r.status_code == 409


def test_assert_company_access_blocks_other():
    u = User(
        id=1,
        email="a@x.com",
        full_name="A",
        hashed_password="x",
        role=UserRole.READ_ONLY,
        company_id=10,
        osgb_id=1,
        is_active=True,
    )
    bind_user_tenant(u)
    assert_company_access(10)
    with pytest.raises(HTTPException) as ei:
        assert_company_access(99)
    assert ei.value.status_code == 403


def test_assert_company_access_osgb_admin_no_company_scope():
    u = User(
        id=2,
        email="b@x.com",
        full_name="B",
        hashed_password="x",
        role=UserRole.COMPANY_ADMIN,
        company_id=None,
        osgb_id=5,
        is_active=True,
    )
    set_tenant(tenant_from_user(u))
    assert_company_access(123)  # company_id yok → no-op
