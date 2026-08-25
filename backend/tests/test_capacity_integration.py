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
        db.add(
            User(
                email="kapasite-uzman@example.com",
                full_name="Kapasite Uzmanı",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.SAFETY_SPECIALIST,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.add(
            User(
                email="kapasite-hekim@example.com",
                full_name="Kapasite Hekimi",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.WORKPLACE_PHYSICIAN,
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


def _login_headers(client: TestClient, email: str) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


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


def test_personal_capacity_is_role_scoped_and_reports_normal_capacity(client):
    seed, admin_headers = _seed(client)

    created = client.post(
        "/api/v1/employees",
        headers=admin_headers,
        json={"company_id": seed["company_id"], "full_name": "Kapasite Personeli"},
    )
    assert created.status_code == 200, created.text

    physician_assignment = client.post(
        "/api/v1/osgb/assignments",
        headers=admin_headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_id": seed["company_id"],
            "professional_id": seed["physician_id"],
            "professional_type": "workplace_physician",
            "start_date": date.today().isoformat(),
            "required_minutes_monthly": 9999,
            "planned_minutes_monthly": 0,
            "actual_minutes_monthly": 0,
            "isg_katip_contract_number": "KAPASITE-KATIP-HEK-002",
        },
    )
    assert physician_assignment.status_code == 200, physician_assignment.text

    specialist_headers = _login_headers(client, "kapasite-uzman@example.com")
    specialist_response = client.get("/api/v1/dashboard/my-capacity", headers=specialist_headers)
    assert specialist_response.status_code == 200, specialist_response.text
    specialist = specialist_response.json()
    assert {row["professional_id"] for row in specialist["professionals"]} == {seed["professional_id"]}
    assert {row["professional_type"] for row in specialist["firms"]} == {"safety_specialist"}
    assert specialist["summary"]["required_minutes_total"] == 20
    assert specialist["summary"]["planned_minutes_total"] == 20
    assert specialist["summary"]["actual_minutes_total"] == 0
    assert specialist["summary"]["remaining_minutes_total"] == 20
    assert specialist["professionals"][0]["capacity_remaining_minutes"] == 11680
    specialist_requirement = specialist["firms"][0]["service_requirement"]["roles"]["safety_specialist"]
    assert specialist_requirement["full_time_threshold_employees"] == 500

    physician_headers = _login_headers(client, "kapasite-hekim@example.com")
    physician_response = client.get("/api/v1/dashboard/my-capacity", headers=physician_headers)
    assert physician_response.status_code == 200, physician_response.text
    physician = physician_response.json()
    assert {row["professional_id"] for row in physician["professionals"]} == {seed["physician_id"]}
    assert {row["professional_type"] for row in physician["firms"]} == {"workplace_physician"}
    assert physician["summary"]["required_minutes_total"] == 10
    assert physician["summary"]["planned_minutes_total"] == 10
    assert physician["summary"]["remaining_minutes_total"] == 10
    assert physician["professionals"][0]["capacity_remaining_minutes"] == 11690
    physician_requirement = physician["firms"][0]["service_requirement"]["roles"]["workplace_physician"]
    assert physician_requirement["full_time_threshold_employees"] == 1000

    osgb = _capacity(client, admin_headers, seed["osgb_id"])
    assert {row["professional_id"] for row in osgb["professionals"]} == {
        seed["professional_id"],
        seed["physician_id"],
    }
    assert osgb["summary"]["normal_capacity_minutes_total"] == 23400


def test_assignment_cannot_exceed_specialist_monthly_capacity(client):
    seed, headers = _seed(client)

    employee = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"company_id": seed["company_id"], "full_name": "Kapasite Sınır Çalışanı"},
    )
    assert employee.status_code == 200, employee.text

    def create_company(name: str, registry: str) -> int:
        response = client.post(
            "/api/v1/companies",
            headers=headers,
            json={
                "name": name,
                "sgk_registry_no": registry,
                "hazard_class": "Tehlikeli",
                "osgb_id": seed["osgb_id"],
            },
        )
        assert response.status_code == 200, response.text
        return response.json()["id"]

    company_at_limit = create_company("Kapasite Sınır İşyeri", "SGK-KAPASITE-LIMIT")
    allowed = client.post(
        "/api/v1/osgb/assignments",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_id": company_at_limit,
            "professional_id": seed["professional_id"],
            "professional_type": "safety_specialist",
            "start_date": date.today().isoformat(),
            "planned_minutes_monthly": 11680,
            "isg_katip_contract_number": "KAPASITE-LIMIT-001",
        },
    )
    assert allowed.status_code == 200, allowed.text

    over_limit_company = create_company("Kapasite Aşım İşyeri", "SGK-KAPASITE-OVER")
    rejected = client.post(
        "/api/v1/osgb/assignments",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_id": over_limit_company,
            "professional_id": seed["professional_id"],
            "professional_type": "safety_specialist",
            "start_date": date.today().isoformat(),
            "planned_minutes_monthly": 1,
            "isg_katip_contract_number": "KAPASITE-OVER-001",
        },
    )
    assert rejected.status_code == 422, rejected.text
    assert "kaydedilemez" in rejected.json()["detail"]
    assert "195 saat" in rejected.json()["detail"]

    assignments = client.get("/api/v1/osgb/assignments", headers=headers)
    assert assignments.status_code == 200, assignments.text
    assert {row["company_id"] for row in assignments.json()} == {seed["company_id"], company_at_limit}
