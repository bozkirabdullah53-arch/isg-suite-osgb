"""0.9.113 — KATİP / görevlendirme sözleşme hazırlık stub (missing-contract-v1)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "katip_prep.db"
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
        User,
        UserRole,
        WorkplaceAssignment,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="KATİP Prep OSGB",
            authorization_number="YETKI-KATIP-1",
            tax_number="9988776655",
            responsible_manager="Prep Yönetici",
            email="katip-prep@test.com",
            phone="02120000000",
            address="Ankara Test",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="KATİP Firma AŞ",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Tehlikeli",
            sgk_registry_no="SGK-K1",
        )
        db.add(company)
        db.flush()
        pro_ok = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Tam Uzman",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="B",
            certificate_number="UZM-OK",
            is_active=True,
        )
        pro_gap = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Eksik Hekim",
            professional_type=ProfessionalType.WORKPLACE_PHYSICIAN,
            certificate_class="A",
            certificate_number="HEK-GAP",
            is_active=True,
        )
        db.add_all([pro_ok, pro_gap])
        db.flush()
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=pro_ok.id,
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                start_date=date.today() - timedelta(days=30),
                required_minutes_monthly=480,
                planned_minutes_monthly=480,
                actual_minutes_monthly=60,
                isg_katip_contract_number="KATIP-OK-1",
                contract_file_name="sozlesme-ok.pdf",
                contract_storage_path="1/assignments/ok.pdf",
                status=AssignmentStatus.ACTIVE,
            )
        )
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=pro_gap.id,
                professional_type=ProfessionalType.WORKPLACE_PHYSICIAN,
                start_date=date.today() - timedelta(days=10),
                required_minutes_monthly=240,
                planned_minutes_monthly=240,
                actual_minutes_monthly=0,
                isg_katip_contract_number=None,
                contract_file_name=None,
                contract_storage_path=None,
                status=AssignmentStatus.ACTIVE,
            )
        )
        db.add(
            User(
                email="katip-admin@test.com",
                full_name="Katip Admin",
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
        json={"email": "katip-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed


def test_health_flag_katip_prep(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.120"
    assert body["katip_prep"] == "missing-contract-v1"


def test_katip_prep_lists_gaps_and_reminder_counts(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/osgb/katip-prep?osgb_id={seed['osgb_id']}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["prep_version"] == "missing-contract-v1"
    assert body["stub"] is True
    assert body["summary"]["active_assignments"] == 2
    assert body["summary"]["complete"] == 1
    assert body["summary"]["gaps"] == 1
    assert body["summary"]["missing_katip_number"] == 1
    assert body["summary"]["missing_contract_file"] == 1
    assert body["reminder_counts"]["ready_to_remind"] == 1
    assert len(body["gaps"]) == 1
    gap = body["gaps"][0]
    assert gap["missing_katip_number"] is True
    assert gap["missing_contract_file"] is True
    assert "KATİP" in gap["reminder_hint"] or "eksik" in gap["reminder_hint"].lower()


def test_katip_prep_csv_export(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/osgb/katip-prep/export.csv?osgb_id={seed['osgb_id']}", headers=headers)
    assert r.status_code == 200, r.text
    assert "text/csv" in (r.headers.get("content-type") or "")
    text = r.content.decode("utf-8-sig")
    assert "assignment_id" in text
    assert "missing_katip_number" in text
    assert "Eksik Hekim" in text or "missing_contract_file" in text
