"""0.9.116 — Profesyonel performans CSV dışa aktarım (ÇSGB)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "pro_perf_csv.db"
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
            name="Perf OSGB",
            authorization_number="YETKI-PERF-1",
            tax_number="9876543210",
            responsible_manager="Yonetici",
            email="perf-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(name="Perf Firma", osgb_id=osgb.id, is_active=True, hazard_class="Tehlikeli")
        db.add(company)
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Zeynep Uzman",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="UZM-PERF",
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
                status=AssignmentStatus.ACTIVE,
                start_date=date.today() - timedelta(days=10),
                required_minutes_monthly=400,
                planned_minutes_monthly=400,
                actual_minutes_monthly=100,
            )
        )
        db.add(
            User(
                email="perf-admin@test.com",
                full_name="Perf Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()
        seed = {"osgb_id": osgb.id, "professional_id": pro.id}

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "perf-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], seed


def test_health_flag_pro_performance_export(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.119"
    assert body["pro_performance_export"] == "csv-v1"
    assert body["csgb_company_snapshot"] == "read-only-v1"


def test_performance_roster_csv(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(
        f"/api/v1/osgb/professionals/performance/export.csv?osgb_id={seed['osgb_id']}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert "text/csv" in (r.headers.get("content-type") or "")
    text = r.content.decode("utf-8-sig")
    assert "professional_id" in text
    assert "Zeynep Uzman" in text


def test_performance_detail_csv(client):
    token, seed = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    pid = seed["professional_id"]
    r = client.get(f"/api/v1/osgb/professionals/{pid}/performance/export.csv", headers=headers)
    assert r.status_code == 200, r.text
    text = r.content.decode("utf-8-sig")
    assert "row_type" in text
    assert "Zeynep Uzman" in text
