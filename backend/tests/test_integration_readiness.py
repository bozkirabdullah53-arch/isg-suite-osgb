"""0.9.127 — İBYS/KATİP/ÇSGB entegrasyon hazırlık checklist (checklist-v1)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "integration_readiness.db"
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
        Employee,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        User,
        UserRole,
        WorkplaceAssignment,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Entegrasyon OSGB",
            authorization_number="YETKI-INT-1",
            tax_number="5544332211",
            responsible_manager="Entegrasyon Yonetici",
            email="integ-osgb@test.com",
            phone="02129998877",
            address="Istanbul Test",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Entegrasyon Firma",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Tehlikeli",
            sgk_registry_no="SGK-INT-1",
        )
        db.add(company)
        db.flush()
        db.add(
            Employee(
                company_id=company.id,
                full_name="Ali Personel",
                national_id_masked="111*****11",
                job_title="Teknisyen",
                start_date=date(2024, 3, 1),
                is_active=True,
            )
        )
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Eksik Uzman",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="B",
            certificate_number="UZM-INT",
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
                start_date=date.today() - timedelta(days=20),
                required_minutes_monthly=480,
                planned_minutes_monthly=480,
                actual_minutes_monthly=0,
                isg_katip_contract_number=None,
                contract_file_name=None,
                contract_storage_path=None,
                status=AssignmentStatus.ACTIVE,
            )
        )
        db.add(
            User(
                email="integ-admin@test.com",
                full_name="Integ Admin",
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
        json={"email": "integ-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed


def test_health_flag_integration_readiness(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.137"
    assert body["integration_readiness"] == "checklist-v1"
    assert body["ibys_export"] == "csv-package-v1"
    assert body["katip_prep"] == "missing-contract-v1"


def test_integration_readiness_checklist(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(
        f"/api/v1/osgb/integration-readiness?osgb_id={seed['osgb_id']}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["readiness_version"] == "checklist-v1"
    assert body["stub"] is True
    assert body["summary"]["ibys_csv_export"] is True
    assert body["summary"]["items_total"] == 3
    codes = [c["code"] for c in body["checklist"]]
    assert codes == ["ibys_csv_export", "katip_gaps", "csgb_pack"]
    by_code = {c["code"]: c for c in body["checklist"]}
    assert by_code["ibys_csv_export"]["ok"] is True
    assert by_code["ibys_csv_export"]["status"] == "ready"
    assert by_code["ibys_csv_export"]["companies"] == 1
    assert by_code["ibys_csv_export"]["employees"] == 1
    assert by_code["katip_gaps"]["gap_count"] >= 1
    assert by_code["katip_gaps"]["ok"] is False
    assert by_code["katip_gaps"]["status"] == "partial"
    assert "csgb_pack" in by_code
    assert "readiness_pct" in by_code["csgb_pack"]
