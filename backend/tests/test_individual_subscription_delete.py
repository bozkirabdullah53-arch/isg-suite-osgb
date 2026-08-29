"""Bireysel abonelik listesinden üye arşivleme."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "indsub.db"
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
    settings.upload_dir = str(tmp_path / "uploads")

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed(client: TestClient) -> dict:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        OsgbOrganization,
        OsgbSubscription,
        SubscriptionStatus,
        User,
        UserRole,
    )

    with SessionLocal() as db:
        org = OsgbOrganization(
            name="Bireysel Uzman Ahmet",
            is_individual=True,
            is_active=True,
            email="ahmet@test.com",
        )
        db.add(org)
        db.flush()
        db.add(
            OsgbSubscription(
                osgb_id=org.id,
                status=SubscriptionStatus.TRIAL,
            )
        )
        specialist = User(
            email="ahmet@test.com",
            full_name="Ahmet Uzman",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.SAFETY_SPECIALIST,
            osgb_id=org.id,
            is_active=True,
        )
        admin = User(
            email="admin@test.com",
            full_name="Global Admin",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add(specialist)
        db.add(admin)
        db.commit()
        db.refresh(specialist)

    r = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"token": r.json()["access_token"], "user_id": specialist.id}


def test_delete_individual_subscription_archives_member(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    listed = client.get("/api/v1/eisa/individual-subscriptions", headers=headers)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json() if item["user_id"] == seed["user_id"])
    assert row.get("osgb_id")

    deleted = client.delete(f"/api/v1/eisa/individual-subscriptions/{seed['user_id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["ok"] is True

    listed2 = client.get("/api/v1/eisa/individual-subscriptions", headers=headers)
    assert listed2.status_code == 200
    assert all(row["user_id"] != seed["user_id"] for row in listed2.json())
