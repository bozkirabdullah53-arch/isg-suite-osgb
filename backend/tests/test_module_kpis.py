"""Modül KPI özeti — OSGB merkezi risk/eğitim/sağlık izleme."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "module_kpi.db"
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


def _seed(client: TestClient) -> tuple[str, int]:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        Company,
        Employee,
        Hazard,
        HazardCategory,
        HealthFitnessStatus,
        HealthRecord,
        HealthRecordType,
        OsgbOrganization,
        RiskAssessment,
        RiskDof,
        TrainingSession,
        TrainingStatus,
        User,
        UserRole,
    )

    today = date.today()
    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="KPI OSGB",
            authorization_number="K-001",
            tax_number="1112223334",
            responsible_manager="Yönetici",
            email="kpi@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="KPI İşyeri",
            sgk_registry_no="SGK-K01",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
        user = User(
            email="admin@test.com",
            full_name="OSGB Admin",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(user)
        db.flush()
        cat = HazardCategory(name="Genel", sort_order=1)
        db.add(cat)
        db.flush()
        hazard = Hazard(category_id=cat.id, code="H-01", name="Mekanik")
        db.add(hazard)
        db.flush()
        employee = Employee(
            company_id=company.id,
            full_name="Test Personel",
            national_id_masked="***",
            job_title="Operatör",
            is_active=True,
        )
        db.add(employee)
        db.flush()

        risk = RiskAssessment(
            risk_code="R-KPI-01",
            company_id=company.id,
            hazard_id=hazard.id,
            activity="Test",
            risk_definition="Test risk",
            probability=4,
            severity=4,
            risk_score=16,
            risk_level="Yüksek",
            status="Açık",
            created_by_id=user.id,
        )
        db.add(risk)
        db.flush()
        db.add(
            RiskDof(
                dof_code="D-KPI-01",
                risk_id=risk.id,
                description="Gecikmiş DÖF",
                term_date=today - timedelta(days=5),
                is_completed=False,
                created_by_id=user.id,
            )
        )
        db.add(
            TrainingSession(
                company_id=company.id,
                title="Temel İSG",
                start_date=today - timedelta(days=400),
                next_training_date=today - timedelta(days=10),
                hazard_class="Tehlikeli",
                instructor_name="Eğitmen",
                status=TrainingStatus.COMPLETED,
                created_by_id=user.id,
            )
        )
        db.add(
            HealthRecord(
                company_id=company.id,
                employee_id=employee.id,
                record_type=HealthRecordType.PERIODIC_EXAM,
                examination_date=today - timedelta(days=400),
                next_examination_date=today - timedelta(days=3),
                fitness_status=HealthFitnessStatus.FIT,
                created_by_id=user.id,
            )
        )
        db.commit()
        osgb_id = osgb.id

    r = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], osgb_id


def test_module_kpis_endpoint(client):
    token, osgb_id = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/operations/module-kpis?osgb_id={osgb_id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["osgb_id"] == osgb_id
    assert body["risk"]["open_dofs"] >= 1
    assert body["risk"]["overdue_dofs"] >= 1
    assert body["training"]["overdue_renewal"] >= 1
    assert body["health"]["overdue"] >= 1
    assert len(body["top_companies"]) >= 1
    assert body["top_companies"][0]["company_name"] == "KPI İşyeri"
