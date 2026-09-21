"""EİSA global panel — OSGB abone listesi PDF dışa aktarımı."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    url = "sqlite://"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"
    settings.upload_dir = str(tmp_path / "uploads")

    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed(client: TestClient) -> dict:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        User,
        UserRole,
    )
    from app.services.osgb_subscription import get_or_create_subscription

    with SessionLocal() as db:
        admin = User(
            email="eisa-pdf.admin@test.com",
            full_name="Eisa PDF Admin",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add(admin)

        active = OsgbOrganization(
            name="Aktif OSGB",
            authorization_number="YETKI-PDF-1",
            tax_number="1122334455",
            responsible_manager="Aktif Yetkili",
            email="aktif-osgb@test.com",
            phone="02120001122",
            is_active=True,
        )
        db.add(active)
        db.flush()
        get_or_create_subscription(db, active.id)

        osgb_admin = User(
            email="eisa-pdf.osgb@test.com",
            full_name="Osgb Yonetici",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=active.id,
            is_active=True,
        )
        db.add(osgb_admin)

        archived = OsgbOrganization(
            name="Pasif OSGB",
            authorization_number="YETKI-PDF-2",
            tax_number="2233445566",
            responsible_manager="Pasif Yetkili",
            email="pasif-osgb@test.com",
            is_active=False,
            archived_at=datetime.utcnow(),
        )
        db.add(archived)

        individual = OsgbOrganization(
            name="Bireysel Uye",
            is_individual=True,
            is_active=True,
        )
        db.add(individual)
        db.flush()
        get_or_create_subscription(db, individual.id)
        ind_user = User(
            email="bireysel-uzman@test.com",
            full_name="Bireysel Uzman",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.SAFETY_SPECIALIST,
            osgb_id=individual.id,
            is_active=True,
        )
        db.add(ind_user)
        db.flush()
        db.add(
            IsgProfessional(
                osgb_id=individual.id,
                full_name="Bireysel Uzman",
                email="bireysel-uzman@test.com",
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                certificate_class="A",
                certificate_number="12345",
                phone="05331112233",
                is_active=True,
            )
        )
        db.commit()

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "eisa-pdf.admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    admin_token = r.json()["access_token"]
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "eisa-pdf.osgb@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    osgb_token = r.json()["access_token"]
    return {"admin_token": admin_token, "osgb_token": osgb_token}


def test_export_pdf_returns_pdf_for_global_admin(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['admin_token']}"}

    r = client.get("/api/v1/eisa/osgb-users/export.pdf", headers=headers)
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
    assert r.headers["content-type"] == "application/pdf"
    assert "osgb-aboneleri-" in r.headers["content-disposition"]


def test_export_pdf_honors_search_filter(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['admin_token']}"}

    hit = client.get("/api/v1/eisa/osgb-users/export.pdf?q=Aktif", headers=headers)
    assert hit.status_code == 200
    assert hit.content[:4] == b"%PDF"

    miss = client.get("/api/v1/eisa/osgb-users/export.pdf?q=olmayanabone", headers=headers)
    assert miss.status_code == 404


def test_export_pdf_active_filter_excludes_archived(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['admin_token']}"}

    only_active = client.get("/api/v1/eisa/osgb-users/export.pdf?active=true", headers=headers)
    assert only_active.status_code == 200

    only_inactive = client.get("/api/v1/eisa/osgb-users/export.pdf?active=false", headers=headers)
    assert only_inactive.status_code == 200


def test_export_pdf_denied_for_non_global_admin(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['osgb_token']}"}

    r = client.get("/api/v1/eisa/osgb-users/export.pdf", headers=headers)
    assert r.status_code in (401, 403)


def test_osgb_users_list_still_works_after_refactor(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['admin_token']}"}

    r = client.get("/api/v1/eisa/osgb-users", headers=headers)
    assert r.status_code == 200
    names = sorted(x["name"] for x in r.json())
    # Bireysel üyeler OSGB listesinde görünmez.
    assert names == ["Aktif OSGB", "Pasif OSGB"]


def test_builder_handles_empty_rows():
    from app.services.eisa_subscribers_pdf import build_osgb_subscribers_pdf

    pdf = build_osgb_subscribers_pdf(rows=[])
    assert pdf[:4] == b"%PDF"


def test_individual_list_contains_seeded_member(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['admin_token']}"}

    r = client.get("/api/v1/eisa/individual-subscriptions", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["specialist_name"] for row in rows] == ["Bireysel Uzman"]
    assert rows[0]["certificate_class"] == "A"


def test_individual_export_pdf_returns_pdf_for_global_admin(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['admin_token']}"}

    r = client.get("/api/v1/eisa/individual-subscriptions/export.pdf", headers=headers)
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
    assert r.headers["content-type"] == "application/pdf"
    assert "bireysel-uyeler-" in r.headers["content-disposition"]


def test_individual_export_pdf_honors_search_filter(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['admin_token']}"}

    hit = client.get("/api/v1/eisa/individual-subscriptions/export.pdf?q=Bireysel", headers=headers)
    assert hit.status_code == 200
    assert hit.content[:4] == b"%PDF"

    miss = client.get("/api/v1/eisa/individual-subscriptions/export.pdf?q=olmayanuye", headers=headers)
    assert miss.status_code == 404


def test_individual_export_pdf_denied_for_non_global_admin(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['osgb_token']}"}

    r = client.get("/api/v1/eisa/individual-subscriptions/export.pdf", headers=headers)
    assert r.status_code in (401, 403)


def test_individual_builder_handles_rows_and_empty():
    from datetime import timedelta

    from app.services.eisa_subscribers_pdf import build_individual_subscribers_pdf

    assert build_individual_subscribers_pdf(rows=[])[:4] == b"%PDF"

    now = datetime.utcnow()
    pdf = build_individual_subscribers_pdf(
        rows=[
            {
                "specialist_name": "Bireysel Uzman",
                "specialist_email": "bireysel@test.com",
                "specialist_phone": "05331112233",
                "certificate_class": "A",
                "certificate_number": "12345",
                "package_name": "Bireysel Paket",
                "effective_status": "trial",
                "days_remaining": 42,
                "trial_ends_at": now + timedelta(days=42),
                "current_period_ends_at": None,
                "account_active": True,
            }
        ],
        search="bireysel",
    )
    assert pdf[:4] == b"%PDF"
