"""İşyeri QR kiosk — check-in / check-out ve süre."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.services.site_verify import build_qr_payload


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "visit_checkin.db"
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


def _seed(client: TestClient, *, assign: bool = True) -> tuple[str, dict, str]:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
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
    from app.services.site_verify import generate_site_verify_code

    code = generate_site_verify_code()
    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Checkin OSGB",
            authorization_number="C-001",
            tax_number="1112223334",
            responsible_manager="Yönetici",
            email="checkin-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Checkin İşyeri",
            sgk_registry_no="SGK-C01",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            site_verify_code=code,
            is_active=True,
        )
        db.add(company)
        db.flush()
        other = Company(
            name="Görevsiz İşyeri",
            sgk_registry_no="SGK-C02",
            hazard_class="Az Tehlikeli",
            osgb_id=osgb.id,
            site_verify_code=generate_site_verify_code(),
            is_active=True,
        )
        db.add(other)
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Checkin Uzman",
            email="checkin-uzman@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            is_active=True,
        )
        db.add(pro)
        db.flush()
        if assign:
            db.add(
                WorkplaceAssignment(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    professional_id=pro.id,
                    professional_type=ProfessionalType.SAFETY_SPECIALIST,
                    start_date=date.today(),
                    status=AssignmentStatus.ACTIVE,
                )
            )
        db.add(
            User(
                email="checkin-uzman@test.com",
                full_name="Checkin Uzman",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.SAFETY_SPECIALIST,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.add(
            User(
                email="checkin-admin@test.com",
                full_name="OSGB Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                company_id=None,
                is_active=True,
            )
        )
        db.commit()
        seed = {
            "company_id": company.id,
            "other_company_id": other.id,
            "other_code": other.site_verify_code,
            "code": code,
            "osgb_id": osgb.id,
        }

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "checkin-uzman@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed, build_qr_payload(seed["company_id"], code)


def test_check_in_out_duration(client):
    token, seed, payload = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}

    cin = client.post(
        "/api/v1/operations/visits/check-in",
        headers=headers,
        json={"site_verify_code": payload},
    )
    assert cin.status_code == 200, cin.text
    body = cin.json()
    assert body["company_id"] == seed["company_id"]
    assert body["checked_in_at"]
    assert body["checked_out_at"] is None
    assert body["status"] == "planned"
    visit_id = body["id"]

    # Aynı QR ile tekrar giriş = 409
    again = client.post(
        "/api/v1/operations/visits/check-in",
        headers=headers,
        json={"site_verify_code": payload},
    )
    assert again.status_code == 409

    from app.core.database import SessionLocal
    from app.models.entities import ServiceVisit

    with SessionLocal() as db:
        v = db.get(ServiceVisit, visit_id)
        v.checked_in_at = datetime.utcnow() - timedelta(minutes=45)
        db.commit()

    cout = client.post(
        "/api/v1/operations/visits/check-out",
        headers=headers,
        json={"site_verify_code": payload},
    )
    assert cout.status_code == 200, cout.text
    out = cout.json()
    assert out["id"] == visit_id
    assert out["checked_out_at"]
    assert out["status"] == "completed"
    assert out["duration_minutes"] >= 44
    assert out["duration_minutes"] <= 46


def test_check_in_forbidden_without_assignment(client):
    token, seed, _ = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    payload = build_qr_payload(seed["other_company_id"], seed["other_code"])
    r = client.post(
        "/api/v1/operations/visits/check-in",
        headers=headers,
        json={"site_verify_code": payload},
    )
    assert r.status_code == 403


def test_ephemeral_reusable_for_check_in_out(client):
    token, seed, _ = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}

    admin = client.post(
        "/api/v1/auth/login",
        json={"email": "checkin-admin@test.com", "password": "TestPass123!"},
    )
    assert admin.status_code == 200, admin.text
    admin_h = {"Authorization": f"Bearer {admin.json()['access_token']}"}

    eph = client.post(
        f"/api/v1/companies/{seed['company_id']}/site-qr/ephemeral",
        headers=admin_h,
    )
    assert eph.status_code == 200, eph.text
    qr = eph.json()["qr_payload"]
    assert qr.startswith("ISGSUITE:WPTEMP:")

    cin = client.post(
        "/api/v1/operations/visits/check-in",
        headers=headers,
        json={"site_verify_code": qr},
    )
    assert cin.status_code == 200, cin.text

    from app.core.database import SessionLocal
    from app.models.entities import ServiceVisit

    with SessionLocal() as db:
        v = db.get(ServiceVisit, cin.json()["id"])
        v.checked_in_at = datetime.utcnow() - timedelta(minutes=10)
        db.commit()

    cout = client.post(
        "/api/v1/operations/visits/check-out",
        headers=headers,
        json={"site_verify_code": qr},
    )
    assert cout.status_code == 200, cout.text
    assert cout.json()["duration_minutes"] >= 9


def test_provision_workplace_kiosk_login(client):
    token, seed, _ = _seed(client)
    from app.core.database import SessionLocal
    from app.models.entities import Company, User, UserRole
    from app.services.osgb_admin import provision_workplace_kiosk_login

    with SessionLocal() as db:
        company = db.get(Company, seed["company_id"])
        user, temp_password, created = provision_workplace_kiosk_login(db, company)
        db.commit()
        assert created is True
        assert user.role == UserRole.COMPANY_ADMIN
        assert user.company_id == company.id
        assert user.osgb_id == company.osgb_id
        assert user.email.startswith("isyeri.")
        assert temp_password
        assert "@kiosk.isgsuite.tr" in user.email
        # İkinci çağrı şifreyi yenilemez
        user2, temp2, created2 = provision_workplace_kiosk_login(db, company)
        db.commit()
        assert created2 is False
        assert user2.id == user.id
        assert temp2 is None
        # Bilinçli sıfırlama
        user3, temp3, created3 = provision_workplace_kiosk_login(db, company, reset_password=True)
        db.commit()
        assert created3 is False
        assert temp3
        assert temp3 != temp_password
