"""Faz 3.1 — CRM fırsat → sözleşme + ilk tahakkuk."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "crm_convert.db"
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


def _seed_admin(client: TestClient) -> tuple[str, dict]:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="CRM OSGB",
            authorization_number="C-001",
            tax_number="1112223334",
            responsible_manager="Yönetici",
            email="crm-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        db.add(
            User(
                email="crm-admin@test.com",
                full_name="CRM Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()
        seed = {"osgb_id": osgb.id}

    r = client.post("/api/v1/auth/login", json={"email": "crm-admin@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed


def test_health_flag_crm_convert(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.110"
    assert body["crm_convert"] == "lead-to-contract-v1"
    assert body["contracts_ui"] == "osgb-monitor-v1"
    assert body["contracts_actions"] == "end-suspend-v1"
    assert body["finance_status"] == "patch-paid-v1"
    assert body["crm_finance_link"] == "company-filter-v1"
    assert body["finance_accrual"] == "monthly-v1"
    assert body["finance_overdue_alert"] == "dashboard-v1"
    assert body["crm_stage_filters"] == "won-lost-v1"


def test_patch_lead_stage(client):
    token, seed = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post(
        "/api/v1/operations/leads",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_name": "Alfa Metal AŞ",
            "contact_name": "Ayşe Yılmaz",
            "employee_count": 40,
            "hazard_class": "Tehlikeli",
            "stage": "new",
            "estimated_monthly_value": 15000,
        },
    )
    assert create.status_code == 200, create.text
    lead_id = create.json()["id"]

    patch = client.patch(
        f"/api/v1/operations/leads/{lead_id}",
        headers=headers,
        json={"stage": "proposal"},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["stage"] == "proposal"


def test_convert_lead_creates_company_contract_finance(client):
    token, seed = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post(
        "/api/v1/operations/leads",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_name": "Beta Gıda Ltd",
            "contact_name": "Mehmet Demir",
            "phone": "05321234567",
            "employee_count": 25,
            "hazard_class": "Az Tehlikeli",
            "stage": "negotiation",
            "estimated_monthly_value": 22000,
        },
    )
    assert create.status_code == 200, create.text
    lead_id = create.json()["id"]

    conv = client.post(f"/api/v1/operations/leads/{lead_id}/convert-to-contract", headers=headers)
    assert conv.status_code == 200, conv.text
    body = conv.json()
    assert body["already_converted"] is False
    assert body["contract"]["contract_number"] == f"CRM-{lead_id}"
    assert body["contract"]["monthly_fee"] == 22000
    assert body["finance_id"] is not None
    assert body["lead"]["stage"] == "won"
    assert body["company_id"] is not None

    from app.core.database import SessionLocal
    from app.models.entities import Company, FinanceTransaction, ServiceContract

    with SessionLocal() as db:
        company = db.get(Company, body["company_id"])
        assert company is not None
        assert company.osgb_id == seed["osgb_id"]
        assert company.site_verify_code
        assert company.authorized_person == "Mehmet Demir"
        contract = db.scalar(select(ServiceContract).where(ServiceContract.contract_number == f"CRM-{lead_id}"))
        assert contract is not None
        assert contract.monthly_fee == 22000
        fin = db.get(FinanceTransaction, body["finance_id"])
        assert fin is not None
        assert fin.amount == 22000
        assert fin.category == "contract"
        assert fin.status == "pending"


def test_convert_lead_idempotent(client):
    token, seed = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post(
        "/api/v1/operations/leads",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_name": "Gama Tekstil",
            "estimated_monthly_value": 8000,
            "stage": "proposal",
        },
    )
    lead_id = create.json()["id"]
    first = client.post(f"/api/v1/operations/leads/{lead_id}/convert-to-contract", headers=headers)
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/operations/leads/{lead_id}/convert-to-contract", headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["already_converted"] is True
    assert second.json()["contract"]["contract_number"] == f"CRM-{lead_id}"

    from app.core.database import SessionLocal
    from app.models.entities import ServiceContract

    with SessionLocal() as db:
        count = db.scalar(
            select(func.count()).select_from(ServiceContract).where(ServiceContract.contract_number == f"CRM-{lead_id}")
        )
        assert count == 1


def test_convert_lost_lead_rejected(client):
    token, seed = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post(
        "/api/v1/operations/leads",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_name": "Delta Kaybedildi",
            "estimated_monthly_value": 5000,
            "stage": "lost",
        },
    )
    lead_id = create.json()["id"]
    conv = client.post(f"/api/v1/operations/leads/{lead_id}/convert-to-contract", headers=headers)
    assert conv.status_code == 400


def test_contracts_list_shows_converted(client):
    token, seed = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post(
        "/api/v1/operations/leads",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_name": "Epsilon Sözleşme",
            "estimated_monthly_value": 12000,
            "stage": "proposal",
        },
    )
    lead_id = create.json()["id"]
    conv = client.post(f"/api/v1/operations/leads/{lead_id}/convert-to-contract", headers=headers)
    assert conv.status_code == 200, conv.text

    listed = client.get("/api/v1/osgb/contracts", headers=headers)
    assert listed.status_code == 200, listed.text
    numbers = [c["contract_number"] for c in listed.json()]
    assert f"CRM-{lead_id}" in numbers


def test_finance_mark_paid_and_contract_end(client):
    token, seed = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post(
        "/api/v1/operations/leads",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_name": "Zeta Finans",
            "estimated_monthly_value": 9000,
            "stage": "proposal",
        },
    )
    lead_id = create.json()["id"]
    conv = client.post(f"/api/v1/operations/leads/{lead_id}/convert-to-contract", headers=headers)
    assert conv.status_code == 200, conv.text
    finance_id = conv.json()["finance_id"]
    contract_id = conv.json()["contract"]["id"]
    assert finance_id is not None

    paid = client.patch(
        f"/api/v1/operations/finance/{finance_id}",
        headers=headers,
        json={"status": "paid"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"

    ended = client.patch(
        f"/api/v1/osgb/contracts/{contract_id}",
        headers=headers,
        json={"status": "ended"},
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "ended"
    assert ended.json()["end_date"] is not None


def test_contract_suspend_end_activate_flow(client):
    token, seed = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post(
        "/api/v1/operations/leads",
        headers=headers,
        json={
            "osgb_id": seed["osgb_id"],
            "company_name": "Theta Sözleşme Aksiyon",
            "estimated_monthly_value": 11000,
            "stage": "proposal",
        },
    )
    lead_id = create.json()["id"]
    conv = client.post(f"/api/v1/operations/leads/{lead_id}/convert-to-contract", headers=headers)
    assert conv.status_code == 200, conv.text
    contract_id = conv.json()["contract"]["id"]

    sus = client.patch(f"/api/v1/osgb/contracts/{contract_id}/suspend", headers=headers)
    assert sus.status_code == 200, sus.text
    assert sus.json()["status"] == "suspended"

    act = client.patch(f"/api/v1/osgb/contracts/{contract_id}/activate", headers=headers)
    assert act.status_code == 200, act.text
    assert act.json()["status"] == "active"

    end = client.patch(f"/api/v1/osgb/contracts/{contract_id}/end", headers=headers)
    assert end.status_code == 200, end.text
    assert end.json()["status"] == "ended"
    assert end.json()["end_date"] is not None

    bad = client.patch(f"/api/v1/osgb/contracts/{contract_id}/suspend", headers=headers)
    assert bad.status_code == 400

    react = client.patch(f"/api/v1/osgb/contracts/{contract_id}/activate", headers=headers)
    assert react.status_code == 200, react.text
    assert react.json()["status"] == "active"
    assert react.json()["end_date"] is None


def test_finance_accrue_month_idempotent(client):
    token, seed = _seed_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    # Manuel sözleşme: CRM convert ilk ay tahakkuku yok → accrue oluşturmalı
    from app.core.database import SessionLocal
    from app.models.entities import Company, ServiceContract
    from datetime import date

    with SessionLocal() as db:
        company = Company(
            name="Iota Tahakkuk",
            sgk_registry_no="SGK-ACCRUE-1",
            osgb_id=seed["osgb_id"],
            is_active=True,
        )
        db.add(company)
        db.flush()
        contract = ServiceContract(
            osgb_id=seed["osgb_id"],
            company_id=company.id,
            contract_number="MAN-ACCRUE-1",
            start_date=date.today().replace(day=1),
            monthly_fee=13000,
            status="active",
        )
        db.add(contract)
        db.commit()

    first = client.post(
        f"/api/v1/operations/finance/accrue-month?osgb_id={seed['osgb_id']}",
        headers=headers,
    )
    assert first.status_code == 200, first.text
    body1 = first.json()
    assert body1["created_count"] >= 1
    assert body1["month"]

    second = client.post(
        f"/api/v1/operations/finance/accrue-month?osgb_id={seed['osgb_id']}",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    body2 = second.json()
    assert body2["created_count"] == 0
    assert body2["skipped_count"] >= 1
