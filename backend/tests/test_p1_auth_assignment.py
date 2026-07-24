"""P1-01 refresh cookie (flag) + P1-06 assignment unique smoke."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, get_password_hash
from app.models.entities import (
    AssignmentStatus,
    Company,
    IsgProfessional,
    OsgbOrganization,
    ProfessionalType,
    User,
    UserRole,
    WorkplaceAssignment,
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "p1pack.db"
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
    settings.auth_refresh_cookie_enabled = False

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def test_refresh_endpoint_404_when_flag_off(client):
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 404


def test_refresh_cookie_flow_when_enabled(client, monkeypatch):
    from app.core.database import SessionLocal
    from app.core.auth_cookies import REFRESH_COOKIE_NAME

    settings.auth_refresh_cookie_enabled = True
    monkeypatch.setattr("app.api.auth.refresh_cookie_enabled", lambda: True)

    with SessionLocal() as db:
        u = User(
            email="refresh@test.com",
            full_name="Refresh User",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.READ_ONLY,
            is_active=True,
            token_version=0,
        )
        db.add(u)
        db.commit()
        uid = u.id

    login = client.post("/api/v1/auth/login", json={"email": "refresh@test.com", "password": "TestPass123!"})
    assert login.status_code == 200, login.text
    body = login.json()
    assert body.get("access_token")
    assert body.get("refresh_cookie") is True
    assert REFRESH_COOKIE_NAME in login.cookies

    # Access ile me
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200

    # Refresh yeni access üretir
    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json().get("access_token")

    settings.auth_refresh_cookie_enabled = False


def test_assignment_ended_allows_reassign(tmp_path):
    """P1-06: ended kayıttan sonra aynı üçlü ile yeni active eklenebilmeli (model düzeyi)."""
    from datetime import date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.models.entities as ent

    url = f"sqlite:///{(tmp_path / 'asg.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        # SQLAlchemy Enum(str) SQLite'da değer olarak 'active' yazar
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_assignment_active_company_pro_type")
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX uq_assignment_active_company_pro_type "
            "ON workplace_assignments (company_id, professional_id, professional_type) "
            "WHERE status IN ('active', 'ACTIVE')"
        )

    with Session() as db:
        o = OsgbOrganization(name="ASG OSGB", is_active=True)
        db.add(o)
        db.flush()
        c = Company(name="ASG Co", osgb_id=o.id, is_active=True)
        p = IsgProfessional(
            osgb_id=o.id,
            full_name="Pro",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            is_active=True,
        )
        db.add_all([c, p])
        db.flush()
        a1 = WorkplaceAssignment(
            osgb_id=o.id,
            company_id=c.id,
            professional_id=p.id,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            start_date=date(2024, 1, 1),
            status=AssignmentStatus.ENDED,
        )
        db.add(a1)
        db.flush()
        a2 = WorkplaceAssignment(
            osgb_id=o.id,
            company_id=c.id,
            professional_id=p.id,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            start_date=date(2025, 1, 1),
            status=AssignmentStatus.ACTIVE,
        )
        db.add(a2)
        db.commit()
        assert db.get(WorkplaceAssignment, a1.id).status == AssignmentStatus.ENDED
        assert db.get(WorkplaceAssignment, a2.id).status == AssignmentStatus.ACTIVE

        a3 = WorkplaceAssignment(
            osgb_id=o.id,
            company_id=c.id,
            professional_id=p.id,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            start_date=date(2025, 6, 1),
            status=AssignmentStatus.ACTIVE,
        )
        db.add(a3)
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
