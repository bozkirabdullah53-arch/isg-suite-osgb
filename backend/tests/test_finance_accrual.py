"""Monthly finance accrual (tahakkuk) for active ServiceContracts."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "finance_accrual.db"
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
            name="Accrual OSGB",
            authorization_number="A-001",
            tax_number="1112223335",
            responsible_manager="Yonetici",
            email="accrual-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        db.add(
            User(
                email="accrual-admin@test.com",
                full_name="Accrual Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()
        seed = {"osgb_id": osgb.id}

    r = client.post("/api/v1/auth/login", json={"email": "accrual-admin@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed


def _seed_contracts(osgb_id: int) -> dict:
    from app.core.database import SessionLocal
    from app.models.entities import Company, ServiceContract

    today = date.today()
    with SessionLocal() as db:
        c1 = Company(name="Accrual Firma 1", osgb_id=osgb_id, is_active=True, hazard_class="Tehlikeli")
        c2 = Company(name="Accrual Firma 2", osgb_id=osgb_id, is_active=True, hazard_class="Az Tehlikeli")
        c3 = Company(name="Accrual Firma 3", osgb_id=osgb_id, is_active=True, hazard_class="Tehlikeli")
        db.add_all([c1, c2, c3])
        db.flush()
        active = ServiceContract(
            osgb_id=osgb_id,
            company_id=c1.id,
            contract_number="ACC-1",
            start_date=today - timedelta(days=60),
            end_date=None,
            monthly_fee=10000,
            status="active",
        )
        zero_fee = ServiceContract(
            osgb_id=osgb_id,
            company_id=c2.id,
            contract_number="ACC-0",
            start_date=today - timedelta(days=30),
            monthly_fee=0,
            status="active",
        )
        suspended = ServiceContract(
            osgb_id=osgb_id,
            company_id=c3.id,
            contract_number="ACC-S",
            start_date=today - timedelta(days=30),
            monthly_fee=5000,
            status="suspended",
        )
        future = ServiceContract(
            osgb_id=osgb_id,
            company_id=c2.id,
            contract_number="ACC-F",
            start_date=today + timedelta(days=10),
            monthly_fee=8000,
            status="active",
        )
        db.add_all([active, zero_fee, suspended, future])
        db.commit()
        return {"active_id": active.id, "osgb_id": osgb_id}


def test_health_flag_finance_accrual(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.112"
    assert body["finance_accrual"] == "monthly-v1"
    assert body["finance_overdue_alert"] == "dashboard-v2"
    assert body["crm_stage_filters"] == "won-lost-v1"


def test_accrue_month_creates_pending_income(client):
    token, seed = _seed_admin(client)
    ids = _seed_contracts(seed["osgb_id"])
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        f"/api/v1/operations/finance/accrue-month?osgb_id={seed['osgb_id']}",
        headers=headers,
        json={},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created_count"] == 1
    assert body["month"] == date.today().strftime("%Y-%m")
    assert len(body["created"]) == 1
    assert body["created"][0]["contract_id"] == ids["active_id"]
    assert body["created"][0]["amount"] == 10000
    key = f"TAHAKKUK-{ids['active_id']}-{body['month']}"
    assert body["created"][0]["key"] == key

    from app.core.database import SessionLocal
    from app.models.entities import FinanceTransaction

    with SessionLocal() as db:
        fin = db.get(FinanceTransaction, body["created"][0]["finance_id"])
        assert fin is not None
        assert fin.transaction_type == "income"
        assert fin.category == "contract"
        assert fin.status == "pending"
        assert key in (fin.description or "")


def test_accrue_month_idempotent(client):
    token, seed = _seed_admin(client)
    _seed_contracts(seed["osgb_id"])
    headers = {"Authorization": f"Bearer {token}"}
    url = f"/api/v1/operations/finance/accrue-month?osgb_id={seed['osgb_id']}"
    first = client.post(url, headers=headers, json={})
    assert first.status_code == 200, first.text
    assert first.json()["created_count"] == 1
    second = client.post(url, headers=headers, json={})
    assert second.status_code == 200, second.text
    assert second.json()["created_count"] == 0

    from app.core.database import SessionLocal
    from app.models.entities import FinanceTransaction

    with SessionLocal() as db:
        count = db.scalar(
            select(func.count()).select_from(FinanceTransaction).where(
                FinanceTransaction.osgb_id == seed["osgb_id"],
                FinanceTransaction.category == "contract",
            )
        )
        assert count == 1
