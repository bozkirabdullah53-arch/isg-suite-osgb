"""0.9.115 — ÇSGB denetim paketi (audit-bundle-v3) + işyeri salt-okunur snapshot."""
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
        company_b = Company(
            name="Diğer Firma Ltd",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Az Tehlikeli",
            sgk_registry_no="SGK-2",
        )
        db.add(company)
        db.add(company_b)
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Ali Uzman",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="UZM-100",
            is_active=True,
        )
        db.add(pro)
        db.flush()
        asg = WorkplaceAssignment(
            osgb_id=osgb.id,
            company_id=company.id,
            professional_id=pro.id,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            status=AssignmentStatus.ACTIVE,
            start_date=date.today() - timedelta(days=30),
            required_minutes_monthly=600,
            planned_minutes_monthly=600,
            actual_minutes_monthly=120,
            isg_katip_contract_number="KATIP-99",
        )
        asg_b = WorkplaceAssignment(
            osgb_id=osgb.id,
            company_id=company_b.id,
            professional_id=pro.id,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            status=AssignmentStatus.ACTIVE,
            start_date=date.today() - timedelta(days=20),
            required_minutes_monthly=300,
            planned_minutes_monthly=300,
            actual_minutes_monthly=60,
            isg_katip_contract_number="KATIP-88",
        )
        db.add(asg)
        db.add(asg_b)
        db.add(
            ServiceContract(
                osgb_id=osgb.id,
                company_id=company.id,
                contract_number="SZ-1",
                start_date=date.today() - timedelta(days=60),
                end_date=date.today() + timedelta(days=300),
                monthly_fee=10000,
                status="active",
            )
        )
        db.add(
            ServiceVisit(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=pro.id,
                visit_date=date.today() - timedelta(days=2),
                duration_minutes=120,
                subject="Saha kontrol",
                status=VisitStatus.COMPLETED,
                notebook_file_name="defter.pdf",
                notebook_storage_path="demo/notebook.pdf",
            )
        )
        db.add(
            ServiceVisit(
                osgb_id=osgb.id,
                company_id=company_b.id,
                professional_id=pro.id,
                visit_date=date.today() - timedelta(days=1),
                duration_minutes=60,
                subject="Diğer saha",
                status=VisitStatus.COMPLETED,
            )
        )
        admin = User(
            email="denetim-admin@test.com",
            full_name="Denetim Admin",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        seed = {
            "osgb_id": osgb.id,
            "company_id": company.id,
            "company_b_id": company_b.id,
        }

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "denetim-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed


def test_health_flag_csgb_company_snapshot(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.138"
    assert body["csgb_pack"] == "audit-bundle-v3"
    assert body["csgb_company_snapshot"] == "read-only-v1"


def test_csgb_audit_pack_includes_notebook_and_capacity(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/osgb/csgb-audit-pack?osgb_id={seed['osgb_id']}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("bundle_version") == "audit-bundle-v3"
    assert body.get("scope", {}).get("mode") == "osgb"
    assert body.get("scope", {}).get("read_only") is True
    codes = {it["code"] for it in body.get("items") or []}
    assert "tespit_defteri" in codes
    assert "kapasite_6331" in codes
    assert "gorevlendirme_katip" in codes
    assert "hizmet_sozlesmesi" in codes
    assert body["osgb"]["notebook_count"] >= 1
    assert body["summary"]["notebooks"] >= 1
    assert isinstance(body.get("missing_items"), list)


def test_csgb_dashboard_summary(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/osgb/csgb-audit-pack/summary?osgb_id={seed['osgb_id']}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "readiness_pct" in body
    assert "missing_items" in body
    assert body.get("bundle_version") == "audit-bundle-v3"


def test_csgb_company_scoped_pack_and_bundle(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    cid = seed["company_id"]
    r = client.get(
        f"/api/v1/osgb/csgb-audit-pack?osgb_id={seed['osgb_id']}&company_id={cid}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scope"]["mode"] == "company"
    assert body["scope"]["company_id"] == cid
    assert body["osgb"]["company_count"] == 1
    assert body["osgb"]["visit_count"] == 1
    assert body["osgb"]["notebook_count"] == 1
    assert body["osgb"]["assignment_count"] == 1

    z = client.get(
        f"/api/v1/osgb/csgb-audit-pack/bundle?osgb_id={seed['osgb_id']}&company_id={cid}",
        headers=headers,
    )
    assert z.status_code == 200, z.text
    assert "application/zip" in (z.headers.get("content-type") or "")
    with ZipFile(BytesIO(z.content)) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "01-checklist.pdf" in names
        manifest = zf.read("manifest.json").decode("utf-8")
        assert "audit-bundle-v3" in manifest
        assert "company" in manifest
        visits = zf.read("03-visits-notebook.json").decode("utf-8")
        assert '"with_notebook": 1' in visits or '"with_notebook":1' in visits
        # Diğer firmanın ziyareti snapshot’ta olmamalı
        assert "Diğer saha" not in visits


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
        man = zf.read("manifest.json").decode("utf-8")
        assert "audit-bundle-v3" in man
