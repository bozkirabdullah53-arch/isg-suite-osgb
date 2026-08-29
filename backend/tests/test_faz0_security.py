"""Faz 0 güvenlik: login lock, health confidential, reset, MFA."""
from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    url = "sqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")

    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"

    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent

    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    from app.core.security import get_password_hash
    from datetime import date
    from app.models.entities import (
        AssignmentStatus,
        Company,
        Employee,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        User,
        UserRole,
        WorkplaceAssignment,
    )
    import app.main as main_mod

    main_mod.engine = engine
    main_mod.SessionLocal = dbmod.SessionLocal
    ent.Base.metadata.create_all(bind=engine)
    app = main_mod.app

    db = dbmod.SessionLocal()
    try:
        osgb = OsgbOrganization(name="Faz0 OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        c = Company(name="Faz0 Firma", hazard_class="Az Tehlikeli", osgb_id=osgb.id)
        db.add(c)
        db.flush()
        professionals = [
            IsgProfessional(
                osgb_id=osgb.id,
                full_name="Hekim",
                email="hekim@example.com",
                professional_type=ProfessionalType.WORKPLACE_PHYSICIAN,
                certificate_number="FAZ0-HEKIM",
                is_active=True,
            ),
            IsgProfessional(
                osgb_id=osgb.id,
                full_name="DSP",
                email="dsp@example.com",
                professional_type=ProfessionalType.OTHER_HEALTH_PERSONNEL,
                certificate_number="FAZ0-DSP",
                is_active=True,
            ),
            IsgProfessional(
                osgb_id=osgb.id,
                full_name="Uzman",
                email="uzman@example.com",
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                certificate_number="FAZ0-UZMAN",
                is_active=True,
            ),
        ]
        db.add_all(professionals)
        db.flush()
        db.add_all([
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=c.id,
                professional_id=pro.id,
                professional_type=pro.professional_type,
                start_date=date(2025, 1, 1),
                status=AssignmentStatus.ACTIVE,
            )
            for pro in professionals
        ])
        db.add_all(
            [
                User(
                    email="hekim@example.com",
                    full_name="Hekim",
                    hashed_password=get_password_hash("HekimPass123!"),
                    role=UserRole.WORKPLACE_PHYSICIAN,
                    osgb_id=osgb.id,
                    company_id=c.id,
                    is_active=True,
                ),
                User(
                    email="dsp@example.com",
                    full_name="DSP",
                    hashed_password=get_password_hash("DspPass12345!"),
                    role=UserRole.OTHER_HEALTH_PERSONNEL,
                    osgb_id=osgb.id,
                    company_id=c.id,
                    is_active=True,
                ),
                User(
                    email="uzman@example.com",
                    full_name="Uzman",
                    hashed_password=get_password_hash("UzmanPass123!"),
                    role=UserRole.SAFETY_SPECIALIST,
                    osgb_id=osgb.id,
                    company_id=c.id,
                    is_active=True,
                ),
                User(
                    email="inactive@example.com",
                    full_name="Pasif",
                    hashed_password=get_password_hash("Inactive123!"),
                    role=UserRole.READ_ONLY,
                    is_active=False,
                ),
                Employee(
                    company_id=c.id,
                    full_name="Personel A",
                    job_title="Teknisyen",
                    department="Uretim",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as tc:
        yield tc


def _login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_inactive_user_cannot_login(client):
    r = _login(client, "inactive@example.com", "Inactive123!")
    assert r.status_code == 401


def test_specialist_login_ok(client):
    r = _login(client, "uzman@example.com", "UzmanPass123!")
    assert r.status_code == 200
    assert r.json().get("access_token")


def test_specialist_register_does_not_create_osgb(client):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Ahmet Yilmaz",
            "email": "yeni.uzman@example.com",
            "password": "QaTest!2026Idea",
            "password_confirm": "QaTest!2026Idea",
            "certificate_class": "C",
            "certificate_number": "ISG-C-QA-20260829",
            "contract_accepted": True,
            "personal_data_accepted": True,
        },
    )
    assert r.status_code in (200, 201), r.text
    assert r.json().get("access_token")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "safety_specialist"
    assert body["osgb_id"] is None
    assert body["company_id"] is None
    orgs = client.get("/api/v1/osgb", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert orgs.status_code == 200
    assert orgs.json() == []


def test_password_reset_flow(client):
    r = client.post("/api/v1/auth/forgot-password", json={"email": "uzman@example.com"})
    assert r.status_code == 200
    import app.core.database as dbmod
    from app.models.entities import User
    from app.services.auth_security import create_password_reset

    db = dbmod.SessionLocal()
    try:
        user = db.query(User).filter_by(email="uzman@example.com").one()
        raw = create_password_reset(db, user)
        db.commit()
    finally:
        db.close()

    r = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "YeniSifre12345!"},
    )
    assert r.status_code == 200
    r = _login(client, "uzman@example.com", "YeniSifre12345!")
    assert r.status_code == 200
    assert r.json().get("access_token")


def test_password_reset_rejects_mismatched_confirmation_without_consuming_token(client):
    import app.core.database as dbmod
    from app.models.entities import User
    from app.services.auth_security import create_password_reset

    db = dbmod.SessionLocal()
    try:
        user = db.query(User).filter_by(email="uzman@example.com").one()
        raw = create_password_reset(db, user)
        db.commit()
    finally:
        db.close()

    mismatch = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw,
            "new_password": "YeniSifre12345!",
            "new_password_confirm": "FarkliSifre12345!",
        },
    )
    assert mismatch.status_code == 422

    completed = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw,
            "new_password": "YeniSifre12345!",
            "new_password_confirm": "YeniSifre12345!",
        },
    )
    assert completed.status_code == 200, completed.text


def test_health_confidential_write_locked_for_dsp(client):
    r = _login(client, "dsp@example.com", "DspPass12345!")
    assert r.status_code == 200
    tok = r.json()["access_token"]
    H = {"Authorization": f"Bearer {tok}"}
    import app.core.database as dbmod
    from app.models.entities import Employee

    db = dbmod.SessionLocal()
    try:
        emp = db.query(Employee).first()
        cid, eid = emp.company_id, emp.id
    finally:
        db.close()

    r = client.post(
        "/api/v1/health-records",
        headers=H,
        json={
            "company_id": cid,
            "employee_id": eid,
            "record_type": "periodic_exam",
            "examination_date": "2026-01-10",
            "fitness_status": "fit",
            "summary": "Periyodik muayene ozeti uygun",
            "confidential_note": "Gizli not deneme",
            "informed_consent": True,
        },
    )
    assert r.status_code == 403


def test_health_confidential_physician_ok_and_dsp_masked(client):
    r = _login(client, "hekim@example.com", "HekimPass123!")
    tok = r.json()["access_token"]
    H = {"Authorization": f"Bearer {tok}"}
    import app.core.database as dbmod
    from app.models.entities import Employee

    db = dbmod.SessionLocal()
    try:
        emp = db.query(Employee).first()
        cid, eid = emp.company_id, emp.id
    finally:
        db.close()

    r = client.post(
        "/api/v1/health-records",
        headers=H,
        json={
            "company_id": cid,
            "employee_id": eid,
            "record_type": "periodic_exam",
            "examination_date": "2026-01-10",
            "fitness_status": "fit",
            "summary": "Periyodik muayene ozeti uygun",
            "confidential_note": "Gizli hekim notu",
            "informed_consent": True,
        },
    )
    assert r.status_code in (200, 201), r.text
    rid = r.json()["id"]
    assert r.json().get("confidential_note") == "Gizli hekim notu"

    r = _login(client, "dsp@example.com", "DspPass12345!")
    Hd = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.get(f"/api/v1/health-records?company_id={cid}", headers=Hd)
    assert r.status_code == 200
    row = next(x for x in r.json() if x["id"] == rid)
    assert row.get("confidential_note") is None


def test_mfa_setup_and_login(client):
    import app.core.database as dbmod
    from app.models.entities import User, UserRole

    db = dbmod.SessionLocal()
    try:
        u = db.query(User).filter_by(email="uzman@example.com").one()
        u.role = UserRole.COMPANY_ADMIN
        db.commit()
    finally:
        db.close()

    r = _login(client, "uzman@example.com", "UzmanPass123!")
    assert r.status_code == 200
    body = r.json()
    assert body.get("mfa_setup_required") is True
    setup_tok = body["mfa_token"]

    r = client.post("/api/v1/security/mfa/setup", headers={"Authorization": f"Bearer {setup_tok}"})
    assert r.status_code == 200
    secret = r.json()["secret"]
    code = pyotp.TOTP(secret).now()
    r = client.post(
        "/api/v1/security/mfa/enable",
        headers={"Authorization": f"Bearer {setup_tok}"},
        json={"code": code},
    )
    assert r.status_code == 200
    assert r.json().get("access_token")
    assert r.json().get("recovery_codes")

    r = _login(client, "uzman@example.com", "UzmanPass123!")
    assert r.json().get("mfa_required") is True
    mfa_tok = r.json()["mfa_token"]
    code = pyotp.TOTP(secret).now()
    r = client.post(
        "/api/v1/auth/mfa/verify",
        headers={"Authorization": f"Bearer {mfa_tok}"},
        json={"code": code},
    )
    assert r.status_code == 200
    assert r.json().get("access_token")


def test_mfa_setup_token_cannot_bypass_via_auth_verify(client):
    """P0: mfa_setup JWT + /auth/mfa/verify ile access alınamaz."""
    import app.core.database as dbmod
    from app.models.entities import User, UserRole

    db = dbmod.SessionLocal()
    try:
        u = db.query(User).filter_by(email="uzman@example.com").one()
        u.role = UserRole.COMPANY_ADMIN
        u.mfa_enabled = False
        db.commit()
    finally:
        db.close()

    r = _login(client, "uzman@example.com", "UzmanPass123!")
    assert r.json().get("mfa_setup_required") is True
    setup_tok = r.json()["mfa_token"]

    r = client.post("/api/v1/security/mfa/setup", headers={"Authorization": f"Bearer {setup_tok}"})
    assert r.status_code == 200
    secret = r.json()["secret"]
    code = pyotp.TOTP(secret).now()

    r = client.post(
        "/api/v1/auth/mfa/verify",
        headers={"Authorization": f"Bearer {setup_tok}"},
        json={"code": code},
    )
    assert r.status_code in (401, 403)
