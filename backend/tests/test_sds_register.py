"""0.9.121 — SDS/PKD kimyasal ürün sicili (chemical-register-v1)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "sds_register.db"
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


def _seed_specialist(client: TestClient) -> tuple[str, int]:
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

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="SDS OSGB",
            authorization_number="YETKI-SDS-1",
            tax_number="1122334455",
            responsible_manager="Yonetici",
            email="sds-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="SDS Firma A.S.",
            tax_number="9988776655",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
        user = User(
            email="sds-uzman@test.com",
            full_name="SDS Uzman",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.SAFETY_SPECIALIST,
            osgb_id=osgb.id,
            company_id=company.id,
            is_active=True,
        )
        db.add(user)
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="SDS Uzman",
            email="sds-uzman@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="UZM-SDS-1",
            is_active=True,
        )
        db.add(pro)
        db.flush()
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=pro.id,
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                status=AssignmentStatus.ACTIVE,
                start_date=date.today() - timedelta(days=30),
                required_minutes_monthly=400,
                planned_minutes_monthly=400,
                actual_minutes_monthly=100,
            )
        )
        db.commit()
        company_id = company.id

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "sds-uzman@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], company_id


def test_health_flag_sds_register(release_flags):
    body = release_flags
    assert body.get("version")
    assert body["sds_register"] == "chemical-register-v1"
    assert body["ghs_label_checklist"] == "ghs-label-checklist-v1"
    assert body["risk_photo_tags"] == "checklist-v1"
    assert body["ai_hazard_hint"] == "keyword-v2"
    assert body["mevzuat_panel"] == "highlights-v1"


def test_sds_meta_and_crud(client):
    token, company_id = _seed_specialist(client)
    headers = {"Authorization": f"Bearer {token}"}

    meta = client.get("/api/v1/sds/meta", headers=headers)
    assert meta.status_code == 200, meta.text
    assert meta.json()["engine"] == "chemical-register-v1"

    bad_cas = client.post(
        "/api/v1/sds",
        headers=headers,
        json={
            "company_id": company_id,
            "product_name": "Aseton",
            "cas_number": "bad",
            "has_sds_file": False,
        },
    )
    assert bad_cas.status_code == 422

    created = client.post(
        "/api/v1/sds",
        headers=headers,
        json={
            "company_id": company_id,
            "product_name": "Aseton",
            "cas_number": "67-64-1",
            "has_sds_file": False,
            "next_review_date": (date.today() + timedelta(days=10)).isoformat(),
            "notes": "Depo A",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["product_name"] == "Aseton"
    assert body["cas_number"] == "67-64-1"
    assert body["review_status"] == "due_soon"
    product_id = body["id"]

    linked = client.post(f"/api/v1/sds/{product_id}/ensure-document", headers=headers)
    assert linked.status_code == 200, linked.text
    assert linked.json()["document_id"]

    listed = client.get("/api/v1/sds", headers=headers, params={"q": "Aseton"})
    assert listed.status_code == 200
    assert any(x["id"] == product_id for x in listed.json())

    summary = client.get("/api/v1/sds/due-summary", headers=headers)
    assert summary.status_code == 200
    s = summary.json()
    assert s["total"] >= 1
    assert s["missing_sds"] >= 1
    assert s["due_soon"] >= 1

    ghs = client.put(
        f"/api/v1/sds/{product_id}/ghs-checklist",
        headers=headers,
        json={"selected": ["GHS02", "GHS07"]},
    )
    assert ghs.status_code == 200, ghs.text
    assert ghs.json()["ghs_selected"] == ["GHS02", "GHS07"]
    assert ghs.json()["ghs_count"] == 2

    got = client.get(f"/api/v1/sds/{product_id}/ghs-checklist", headers=headers)
    assert got.status_code == 200
    assert got.json()["engine"] == "ghs-label-checklist-v1"
    assert got.json()["selected"] == ["GHS02", "GHS07"]


def test_sds_branch_must_belong_to_company_and_be_active(client):
    from app.core.database import SessionLocal
    from app.models.entities import Branch, Company

    token, company_id = _seed_specialist(client)
    headers = {"Authorization": f"Bearer {token}"}

    with SessionLocal() as db:
        company = db.get(Company, company_id)
        own_branch = Branch(company_id=company_id, name="Merkez Şube", is_active=True)
        inactive_branch = Branch(company_id=company_id, name="Kapalı Şube", is_active=False)
        foreign_company = Company(
            name="Başka Firma",
            osgb_id=company.osgb_id,
            is_active=True,
        )
        db.add_all([own_branch, inactive_branch, foreign_company])
        db.flush()
        foreign_branch = Branch(
            company_id=foreign_company.id,
            name="Yabancı Şube",
            is_active=True,
        )
        db.add(foreign_branch)
        db.commit()
        own_branch_id = own_branch.id
        inactive_branch_id = inactive_branch.id
        foreign_branch_id = foreign_branch.id

    created = client.post(
        "/api/v1/sds",
        headers=headers,
        json={
            "company_id": company_id,
            "branch_id": own_branch_id,
            "product_name": "Şubeye Bağlı Kimyasal",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["branch_id"] == own_branch_id

    for branch_id in (foreign_branch_id, inactive_branch_id, 999_999):
        rejected = client.post(
            "/api/v1/sds",
            headers=headers,
            json={
                "company_id": company_id,
                "branch_id": branch_id,
                "product_name": "Geçersiz Şube Kimyasalı",
            },
        )
        assert rejected.status_code == 400, rejected.text


def test_company_admin_cannot_create_sds(client):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="CA SDS OSGB",
            authorization_number="YETKI-CA-SDS",
            tax_number="5566778800",
            responsible_manager="CA",
            email="ca-sds-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        db.add(
            User(
                email="ca-sds@test.com",
                full_name="CA Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ca-sds@test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    r = client.post(
        "/api/v1/sds",
        headers={"Authorization": f"Bearer {token}"},
        json={"company_id": 1, "product_name": "X"},
    )
    assert r.status_code in (401, 403)
