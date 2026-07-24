"""P1-05: Company.name unique is scoped to osgb_id."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.entities import Company, OsgbOrganization, User, UserRole


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "company_scope.db"
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


def _seed_two_osgbs_and_admin():
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        o1 = OsgbOrganization(name="OSGB Alpha Scope", is_active=True)
        o2 = OsgbOrganization(name="OSGB Beta Scope", is_active=True)
        db.add_all([o1, o2])
        db.flush()
        admin = User(
            email="scope-admin@test.com",
            full_name="Scope Admin",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        return o1.id, o2.id


def test_same_company_name_allowed_across_osgbs(client):
    o1, o2 = _seed_two_osgbs_and_admin()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "scope-admin@test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r1 = client.post(
        "/api/v1/companies",
        headers=headers,
        json={
            "name": "Aynı İşyeri AŞ",
            "osgb_id": o1,
            "hazard_class": "Tehlikeli",
            "sgk_registry_no": "SGK-SCOPE-1",
        },
    )
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        "/api/v1/companies",
        headers=headers,
        json={
            "name": "Aynı İşyeri AŞ",
            "osgb_id": o2,
            "hazard_class": "Tehlikeli",
            "sgk_registry_no": "SGK-SCOPE-2",
        },
    )
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] != r2.json()["id"]

    # Same OSGB → 409
    r3 = client.post(
        "/api/v1/companies",
        headers=headers,
        json={
            "name": "Aynı İşyeri AŞ",
            "osgb_id": o1,
            "hazard_class": "Az Tehlikeli",
            "sgk_registry_no": "SGK-SCOPE-3",
        },
    )
    assert r3.status_code == 409


def test_company_name_taken_helper():
    from app.api.companies import _company_name_taken
    from app.core.database import SessionLocal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        o = OsgbOrganization(name="Helper OSGB", is_active=True)
        db.add(o)
        db.flush()
        db.add(Company(name="X", osgb_id=o.id, is_active=True))
        db.commit()
        assert _company_name_taken(db, "X", o.id) is True
        assert _company_name_taken(db, "X", o.id + 99) is False
        assert _company_name_taken(db, "Y", o.id) is False
