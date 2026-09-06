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
    settings.environment = "development"
    settings.auth_refresh_cookie_force_off = False
    monkeypatch.setattr("app.api.auth.refresh_cookie_enabled", lambda: True)
    monkeypatch.setattr("app.core.auth_cookies.refresh_cookie_enabled", lambda: True)

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Refresh Test OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        u = User(
            email="refresh@test.com",
            full_name="Refresh User",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.READ_ONLY,
            osgb_id=osgb.id,
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
    assert body.get("expires_in")
    assert REFRESH_COOKIE_NAME in login.cookies

    # Access ile me
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200

    # Refresh yeni access üretir
    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json().get("access_token")

    settings.auth_refresh_cookie_enabled = False


def test_me_bootstraps_refresh_cookie_for_existing_access_session(client, monkeypatch):
    """Existing sessions must survive the short access-token window."""
    from app.core.auth_cookies import REFRESH_COOKIE_NAME
    from app.core.database import SessionLocal

    settings.auth_refresh_cookie_enabled = True
    settings.environment = "development"
    settings.auth_refresh_cookie_force_off = False
    monkeypatch.setattr("app.api.auth.refresh_cookie_enabled", lambda: True)
    monkeypatch.setattr("app.core.auth_cookies.refresh_cookie_enabled", lambda: True)

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Existing Session OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        user = User(
            email="existing-session@test.com",
            full_name="Existing Session User",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            company_id=None,
            is_active=True,
            token_version=0,
        )
        db.add(user)
        db.commit()
        token = create_access_token(str(user.id), token_version=0, minutes=15)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert REFRESH_COOKIE_NAME in client.cookies

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


@pytest.mark.parametrize("legacy_minutes", [0, -1])
def test_assignment_list_and_end_preserve_legacy_rows(client, legacy_minutes):
    """A persisted row must not fail serialization after end has committed."""
    from datetime import date, timedelta
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Legacy Assignment OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Legacy Assignment Company", osgb_id=osgb.id, is_active=True)
        professional = IsgProfessional(
            osgb_id=osgb.id, full_name="Legacy Professional",
            professional_type=ProfessionalType.SAFETY_SPECIALIST, is_active=True,
        )
        admin = User(
            email="legacy-assignment@example.com", full_name="Assignment Admin",
            hashed_password="unused", role=UserRole.GLOBAL_ADMIN, is_active=True,
            token_version=0,
        )
        db.add_all([company, professional, admin])
        db.flush()
        row = WorkplaceAssignment(
            osgb_id=osgb.id, company_id=company.id, professional_id=professional.id,
            professional_type=professional.professional_type,
            start_date=date.today() + timedelta(days=10), end_date=date.today(),
            required_minutes_monthly=legacy_minutes,
            planned_minutes_monthly=legacy_minutes,
            actual_minutes_monthly=legacy_minutes,
            status=AssignmentStatus.ACTIVE,
        )
        db.add(row)
        db.commit()
        assignment_id = row.id
        token = create_access_token(str(admin.id), token_version=0)
        create_payload = {
            "osgb_id": osgb.id, "company_id": company.id,
            "professional_id": professional.id,
            "professional_type": professional.professional_type.value,
            "start_date": row.start_date.isoformat(),
            "end_date": row.end_date.isoformat(),
            "isg_katip_contract_number": "LEGACY-REGRESSION-001",
        }

    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get("/api/v1/osgb/assignments", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [assignment_id]
    ended = client.patch(f"/api/v1/osgb/assignments/{assignment_id}/end", headers=headers)
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "ended"
    assert ended.json()["end_date"] == date.today().isoformat()
    for field in ("required_minutes_monthly", "planned_minutes_monthly", "actual_minutes_monthly"):
        assert listed.json()[0][field] == legacy_minutes
        assert ended.json()[field] == legacy_minutes

    with SessionLocal() as db:
        persisted = db.get(WorkplaceAssignment, assignment_id)
        assert persisted.status == AssignmentStatus.ENDED
        assert persisted.start_date.isoformat() == create_payload["start_date"]
        assert persisted.actual_minutes_monthly == legacy_minutes

    # New inputs retain strict validation even when legacy output is readable.
    invalid_dates = client.post("/api/v1/osgb/assignments", headers=headers, json=create_payload)
    assert invalid_dates.status_code == 422, invalid_dates.text
    create_payload["end_date"] = None
    for field in ("required_minutes_monthly", "planned_minutes_monthly", "actual_minutes_monthly"):
        invalid_minutes = client.post(
            "/api/v1/osgb/assignments", headers=headers,
            json={**create_payload, field: -1},
        )
        assert invalid_minutes.status_code == 422, invalid_minutes.text
