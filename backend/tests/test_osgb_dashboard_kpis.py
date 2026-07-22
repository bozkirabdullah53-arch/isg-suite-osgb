"""0.9.112 — OSGB home finance overdue + active expiring-contract KPIs (uncapped counts)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "osgb_dashboard_kpis.db"
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
        Company,
        FinanceTransaction,
        OsgbOrganization,
        ServiceContract,
        User,
        UserRole,
    )

    today = date.today()
    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="KPI OSGB",
            authorization_number="YETKI-KPI-112",
            tax_number="9876543210",
            responsible_manager="KPI Yonetici",
            email="kpi-osgb@test.com",
            phone="02120001122",
            address="Istanbul KPI Cad. 1",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="KPI Firma",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Tehlikeli",
            sgk_registry_no="SGK-KPI-1",
        )
        db.add(company)
        db.flush()

        overdue_amounts = []
        for i in range(26):
            amt = 1000 + i
            overdue_amounts.append(amt)
            db.add(
                FinanceTransaction(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    transaction_type="income",
                    category="contract",
                    amount=amt,
                    transaction_date=today - timedelta(days=40),
                    due_date=today - timedelta(days=10 + (i % 5)),
                    status="pending",
                    description=f"overdue-{i}",
                )
            )

        db.add(
            FinanceTransaction(
                osgb_id=osgb.id,
                company_id=company.id,
                transaction_type="income",
                category="service",
                amount=5000,
                transaction_date=today,
                due_date=today + timedelta(days=7),
                status="pending",
                description="due-soon",
            )
        )

        db.add(
            ServiceContract(
                osgb_id=osgb.id,
                company_id=company.id,
                contract_number="SOZ-ACTIVE-EXP",
                start_date=today - timedelta(days=300),
                end_date=today + timedelta(days=15),
                monthly_fee=12000,
                status="Active",
            )
        )
        db.add(
            ServiceContract(
                osgb_id=osgb.id,
                company_id=company.id,
                contract_number="SOZ-ENDED-EXP",
                start_date=today - timedelta(days=400),
                end_date=today + timedelta(days=10),
                monthly_fee=8000,
                status="ended",
            )
        )

        db.add(
            User(
                email="kpi-admin@test.com",
                full_name="KPI Admin",
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
            "overdue_count": 26,
            "overdue_amount": sum(overdue_amounts),
            "due_soon_count": 1,
            "due_soon_amount": 5000,
        }

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "kpi-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed


def test_health_flag_osgb_home_kpis_v3(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.135"
    assert body["finance_overdue_alert"] == "dashboard-v2"
    assert body["osgb_home_kpis"] == "finance-contracts-sds-v3"
    assert body["osgb_sds_due"] == "dashboard-v1"
    assert body["integration_readiness"] == "checklist-v1"
    assert body["csgb_pack"] == "audit-bundle-v3"


def test_osgb_dashboard_finance_and_contract_kpis_uncapped(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/operations/dashboard?osgb_id={seed['osgb_id']}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kpi_version"] == "dashboard-finance-contracts-sds-v3"
    assert body["finance_overdue_count"] == seed["overdue_count"]
    assert body["finance_overdue_count"] > 20
    assert body["finance_overdue_amount"] == seed["overdue_amount"]
    assert body["finance_due_soon_count"] == seed["due_soon_count"]
    assert body["finance_due_soon_amount"] == seed["due_soon_amount"]
    assert body["upcoming_contract_expiries"] == 1
    assert len(body.get("upcoming_contracts") or []) == 1
    assert body["upcoming_contracts"][0]["contract_number"] == "SOZ-ACTIVE-EXP"
    assert any(a.get("level") == "critical" for a in (body.get("finance_alerts") or []))
    assert len(body.get("contract_alerts") or []) >= 1
    assert body["sds_overdue_count"] == 0
    assert body["sds_due_soon_count"] == 0


def test_osgb_dashboard_sds_due_kpis(client):
    """0.9.123 — Ana Panel SDS gecikmiş / yaklaşan sayaçları."""
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import ChemicalProduct, Company, OsgbOrganization, User, UserRole

    today = date.today()
    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="SDS KPI OSGB",
            authorization_number="YETKI-SDS-KPI",
            tax_number="1122334455",
            responsible_manager="Yonetici",
            email="sds-kpi-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="SDS KPI Firma",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Tehlikeli",
            sgk_registry_no="SGK-SDS-KPI",
        )
        db.add(company)
        db.flush()
        admin = User(
            email="sds-kpi-admin@test.com",
            full_name="SDS KPI Admin",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add_all(
            [
                ChemicalProduct(
                    company_id=company.id,
                    product_name="Asit",
                    has_sds_file=True,
                    next_review_date=today - timedelta(days=3),
                    created_by_id=admin.id,
                    is_active=True,
                ),
                ChemicalProduct(
                    company_id=company.id,
                    product_name="Baz",
                    has_sds_file=False,
                    next_review_date=today + timedelta(days=10),
                    created_by_id=admin.id,
                    is_active=True,
                ),
                ChemicalProduct(
                    company_id=company.id,
                    product_name="Yag",
                    has_sds_file=True,
                    next_review_date=today + timedelta(days=60),
                    created_by_id=admin.id,
                    is_active=True,
                ),
            ]
        )
        db.commit()
        osgb_id = osgb.id

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "sds-kpi-admin@test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r = client.get(f"/api/v1/operations/dashboard?osgb_id={osgb_id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kpi_version"] == "dashboard-finance-contracts-sds-v3"
    assert body["sds_overdue_count"] == 1
    assert body["sds_due_soon_count"] == 1
    assert any("gecikmis" in (a.get("text") or "") for a in body.get("sds_alerts") or [])
    assert any("30 gun" in (a.get("text") or "") for a in body.get("sds_alerts") or [])
