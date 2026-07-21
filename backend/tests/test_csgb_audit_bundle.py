"""0.9.111 — ÇSGB denetim paketi (audit-bundle-v2) ZIP + checklist sıkılaştırma."""
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "csgb_bundle.db"
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


def _seed(client: TestClient) -> tuple[str, dict]:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        ServiceContract,
        ServiceVisit,
        User,
        UserRole,
        VisitStatus,
        WorkplaceAssignment,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Denetim OSGB",
            authorization_number="YETKI-778899",
            tax_number="1234567891",
            responsible_manager="Ayşe Yönetici",
            email="denetim-osgb@test.com",
            phone="02121234567",
            address="İstanbul Test Cad. 1",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Denetim Firma AŞ",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Tehlikeli",
            sgk_registry_no="SGK-1",
        )
        db.add(company)
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Ali Uzman",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="B",
            certificate_number="UZM-100",
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
                start_date=date.today() - timedelta(days=90),
                required_minutes_monthly=480,
                planned_minutes_monthly=480,
                actual_minutes_monthly=120,
                isg_katip_contract_number="KATIP-99",
                status=AssignmentStatus.ACTIVE,
            )
        )
        db.add(
            ServiceContract(
                osgb_id=osgb.id,
                company_id=company.id,
                contract_number="SOZ-1",
                start_date=date.today() - timedelta(days=60),
                monthly_fee=12000,
                status="active",
            )
        )
        db.add(
            ServiceVisit(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=pro.id,
                visit_date=date.today() - timedelta(days=3),
                duration_minutes=120,
                subject="Saha denetimi",
                notebook_file_name="defter.pdf",
                notebook_storage_path="1/visits/defter.pdf",
                status=VisitStatus.COMPLETED,
            )
        )
        db.add(
            User(
                email="denetim-admin@test.com",
                full_name="Denetim Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()
        seed = {"osgb_id": osgb.id, "company_id": company.id}

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "denetim-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed


def test_health_flag_csgb_audit_bundle_v2(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.112"
    assert body["csgb_pack"] == "audit-bundle-v2"


def test_csgb_audit_pack_includes_notebook_and_capacity(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/osgb/csgb-audit-pack?osgb_id={seed['osgb_id']}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("bundle_version") == "audit-bundle-v2"
    codes = {it["code"] for it in body.get("items") or []}
    assert "tespit_defteri" in codes
    assert "kapasite_6331" in codes
    assert "gorevlendirme_katip" in codes
    assert "hizmet_sozlesmesi" in codes
    assert body["osgb"]["notebook_count"] >= 1
    assert body["summary"]["notebooks"] >= 1


def test_csgb_audit_bundle_zip_download(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/osgb/csgb-audit-pack/bundle?osgb_id={seed['osgb_id']}", headers=headers)
    assert r.status_code == 200, r.text
    assert "application/zip" in (r.headers.get("content-type") or "")
    raw = r.content
    assert len(raw) > 100
    with ZipFile(BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "01-checklist.pdf" in names
        assert "01-checklist.json" in names
        assert "02-assignments.json" in names
        assert "03-visits-notebook.json" in names
        assert "04-contracts.json" in names
        assert "05-capacity-snapshot.json" in names
        assert "manifest.json" in names
        pdf = zf.read("01-checklist.pdf")
        assert pdf[:4] == b"%PDF"
        visits = zf.read("03-visits-notebook.json").decode("utf-8")
        assert "has_notebook" in visits
        assert '"with_notebook": 1' in visits or '"with_notebook":1' in visits
