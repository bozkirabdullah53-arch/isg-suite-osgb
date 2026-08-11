"""Kapasite hesabının çalışan/NACE API değişimleriyle güncellendiği akış testleri."""
from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "capacity.db"
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


def _seed(client: TestClient) -> tuple[dict, dict[str, str]]:
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
            name="Kapasite Test OSGB",
            authorization_number="KAPASITE-TEST-001",
            tax_number="1234567890",
            responsible_manager="Kapasite Yönetici",
            email="kapasite-test@example.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Kapasite Test İşyeri",
            osgb_id=osgb.id,
            sgk_registry_no="SGK-KAPASITE-1",
            hazard_class="Tehlikeli",
            is_active=True,
        )
        db.add(company)
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Kapasite Uzmanı",
            email="kapasite-uzman@example.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="KAPASITE-UZM-001",
            is_active=True,
        )
        db.add(pro)
        db.flush()
        physician = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Kapasite Hekimi",
            email="kapasite-hekim@example.com",
            professional_type=ProfessionalType.WORKPLACE_PHYSICIAN,
            certificate_class="A",
            certificate_number="KAPASITE-HEK-001",
            is_active=True,
        )
        db.add(physician)
        db.flush()
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=pro.id,
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                start_date=date.today(),
                required_minutes_monthly=999,
                planned_minutes_monthly=0,
                actual_minutes_monthly=0,
                isg_katip_contract_number="KAPASITE-KATIP-001",
                status=AssignmentStatus.ACTIVE,
            )
        )
        db.add(
            User(
                email="kapasite-admin@example.com",
                full_name="Kapasite Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()
        seed = {
            "osgb_id": osgb.id,
            "company_id": company.id,
            "professional_id": pro.id,
            "physician_id": physician.id,
        }

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "kapasite-admin@example.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    return seed, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _capacity(client: TestClient, headers: dict[str, str], osgb_id: int) -> dict:
    response = client.get(f"/api/v1/osgb/capacity?osgb_id={osgb_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_employee_and_nace_changes_recalculate_authoritative_minutes(client):
    seed, headers = _seed(client)

    initial = _capacity(client, headers, seed["osgb_id"])
    workplace = initial["workplaces"][0]
    assert workplace["employee_count"] == 0
    assert workplace["specialist_requirement"]["required_minutes"] == 0

    created = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"company_id": seed["company_id"], "full_name": "Aktif Çalışan"},
    )
    assert created.status_code == 200, created.text
    employee_id = created.json()["id"]
    one_employee = _capacity(client, headers, seed["osgb_id"])
    assert one_employee["workplaces"][0]["employee_count"] == 1
    assert one_employee["workplaces"][0]["specialist_requirement"]["required_minutes"] == 20
    specialist_firm = next(row for row in one_employee["firms"] if row["professional_type"] == "safety_specialist")
    assert specialist_firm["legal_required_minutes"] == 20

    created_physician_assignment = client.post(
        "/api/v1/osgb/assignments",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_id": seed["company_id"],
            "professional_id": seed["physician_id"],
            "professional_type": "workplace_physician",
            "start_date": date.today().isoformat(),
            "required_minutes_monthly": 9999,
            "planned_minutes_monthly": 0,
            "actual_minutes_monthly": 0,
            "isg_katip_contract_number": "KAPASITE-KATIP-HEK-001",
        },
    )
    assert created_physician_assignment.status_code == 200, created_physician_assignment.text
    assert created_physician_assignment.json()["required_minutes_monthly"] == 10

    changed_hazard = client.put(
        f"/api/v1/companies/{seed['company_id']}",
        headers=headers,
        json={"hazard_class": "Az Tehlikeli", "nace_code": None},
    )
    assert changed_hazard.status_code == 200, changed_hazard.text
    low = _capacity(client, headers, seed["osgb_id"])
    assert low["workplaces"][0]["specialist_requirement"]["required_minutes"] == 10

    changed_nace = client.put(
        f"/api/v1/companies/{seed['company_id']}",
        headers=headers,
        json={"nace_code": "24.10.01"},
    )
    assert changed_nace.status_code == 200, changed_nace.text
    very_hazardous = _capacity(client, headers, seed["osgb_id"])
    assert very_hazardous["workplaces"][0]["hazard_class"] == "Çok Tehlikeli"
    assert very_hazardous["workplaces"][0]["specialist_requirement"]["required_minutes"] == 40

    deactivated = client.delete(f"/api/v1/employees/{employee_id}", headers=headers)
    assert deactivated.status_code == 200, deactivated.text
    reactivated = client.put(
        f"/api/v1/employees/{employee_id}",
        headers=headers,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200, reactivated.text
    active_again = _capacity(client, headers, seed["osgb_id"])
    assert active_again["workplaces"][0]["specialist_requirement"]["required_minutes"] == 40

    deactivated_again = client.delete(f"/api/v1/employees/{employee_id}", headers=headers)
    assert deactivated_again.status_code == 200, deactivated_again.text
    empty = _capacity(client, headers, seed["osgb_id"])
    assert empty["workplaces"][0]["employee_count"] == 0
    assert empty["workplaces"][0]["specialist_requirement"]["required_minutes"] == 0


def test_bulk_employee_import_recalculates_active_population(client):
    seed, headers = _seed(client)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Adı Soyadı"])
    sheet.append(["Toplu Çalışan 1"])
    sheet.append(["Toplu Çalışan 2"])
    buffer = BytesIO()
    workbook.save(buffer)

    response = client.post(
        f"/api/v1/employees/import-excel?company_id={seed['company_id']}",
        headers=headers,
        files={
            "file": (
                "personel.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 2
    capacity = _capacity(client, headers, seed["osgb_id"])
    assert capacity["workplaces"][0]["employee_count"] == 2
    assert capacity["workplaces"][0]["specialist_requirement"]["required_minutes"] == 40
