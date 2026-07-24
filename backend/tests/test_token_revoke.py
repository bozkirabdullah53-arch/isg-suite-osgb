"""JWT revoke — logout denylist + token_version bump."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.services.token_revoke import bump_token_version, is_jti_revoked, revoke_jti


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "revoke.db"
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


def _seed_user():
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import User, UserRole

    with SessionLocal() as db:
        user = User(
            email="revoke@test.com",
            full_name="Revoke User",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            is_active=True,
            token_version=0,
        )
        db.add(user)
        db.commit()
        return user.id


def test_logout_revokes_token(client):
    _seed_user()
    login = client.post("/api/v1/auth/login", json={"email": "revoke@test.com", "password": "TestPass123!"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    out = client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 200, out.text

    blocked = client.get("/api/v1/auth/me", headers=headers)
    assert blocked.status_code == 401


def test_token_version_bump_invalidates(client):
    uid = _seed_user()
    token = create_access_token(str(uid), token_version=0)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    from app.core.database import SessionLocal
    from app.models.entities import User

    with SessionLocal() as db:
        user = db.get(User, uid)
        bump_token_version(user)
        db.commit()

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_revoke_helpers(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent

    url = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.SessionLocal = sessionmaker(bind=engine)
    ent.Base.metadata.create_all(bind=engine)
    with dbmod.SessionLocal() as db:
        assert is_jti_revoked(db, None) is False
        revoke_jti(db, jti="abc123", user_id=None, expires_at=datetime.utcnow() + timedelta(hours=1))
        db.commit()
        assert is_jti_revoked(db, "abc123") is True
