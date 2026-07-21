"""0.9.115 â€” Ä°BYS export stub (employee/company CSV ZIP package)."""
from __future__ import annotations

from datetime import date
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "ibys_export.db"
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
    from app.models.entities import Company, Employee, OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Ä°BYS OSGB",
            authorization_number="YETKI-IBYS-1",
            tax_number="1122334455",
            responsible_manager="Ä°bys YÃ¶netici",
            email="ibys-osgb@test.com",
            phone="02121112233",
            address="Ä°zmir Test",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Ä°BYS Firma Ltd",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Az Tehlikeli",
            sgk_registry_no="SGK-IBYS-1",
        )
        db.add(company)
        db.flush()
        db.add(
            Employee(
                company_id=company.id,
                full_name="AyÅŸe Personel",
                national_id_masked="123*****89",
                job_title="OperatÃ¶r",
                start_date=date(2024, 1, 15),
                is_active=True,
            )
        )
        db.add(
            User(
                email="ibys-admin@test.com",
                full_name="Ä°bys Admin",
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
        json={"email": "ibys-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed


def test_health_flag_ibys_export(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.118"
    assert body["ibys_export"] == "csv-package-v1"
    assert body["katip_prep"] == "missing-contract-v1"


def test_ibys_export_summary(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/osgb/ibys-export?osgb_id={seed['osgb_id']}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["export_version"] == "csv-package-v1"
    assert body["stub"] is True
    assert body["summary"]["companies"] == 1
    assert body["summary"]["employees"] == 1
    assert body["summary"]["active_employees"] == 1


def test_ibys_export_zip_package(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/osgb/ibys-export/package?osgb_id={seed['osgb_id']}", headers=headers)
    assert r.status_code == 200, r.text
    assert "application/zip" in (r.headers.get("content-type") or "")
    with ZipFile(BytesIO(r.content)) as zf:
        names = set(zf.namelist())
        assert "00-README.txt" in names
        assert "01-isyerleri.csv" in names
        assert "02-personel.csv" in names
        firms = zf.read("01-isyerleri.csv").decode("utf-8-sig")
        people = zf.read("02-personel.csv").decode("utf-8-sig")
        assert "Ä°BYS Firma Ltd" in firms or "IBYS Firma" in firms
        assert "AyÅŸe Personel" in people or "Personel" in people
