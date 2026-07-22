"""0.9.131 — Tatbikat yönetimi smoke tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "drills.db"
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
    settings.upload_dir = str(tmp_path / "uploads")

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed(client: TestClient) -> dict:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Drill OSGB",
            authorization_number="YETKI-DRILL-1",
            tax_number="9988776655",
            responsible_manager="Drill Yonetici",
            email="drill-osgb@test.com",
            phone="02120001122",
            address="Izmir",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Drill Firma",
            osgb_id=osgb.id,
            tax_number="1234567890",
            is_active=True,
        )
        db.add(company)
        db.flush()
        db.add(
            User(
                email="drill-uzman@test.com",
                full_name="Drill Uzman",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.SAFETY_SPECIALIST,
                osgb_id=osgb.id,
                company_id=company.id,
                is_active=True,
            )
        )
        db.commit()
        company_id = company.id

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "drill-uzman@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return {"token": r.json()["access_token"], "company_id": company_id}


def test_health_tatbikat_flag(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.134"
    assert body["tatbikat"] == "drill-management-v1"


def test_create_list_export_deactivate(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}

    created = client.post(
        "/api/v1/drills",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "drill_type": "Yangın",
            "drill_date": "2026-07-20",
            "start_time": "10:00",
            "end_time": "11:00",
            "responsible": "Ahmet Uzman",
            "assembly_area": "Otopark",
            "status": "yapildi",
            "scenario": "Yangın alarmı sonrası tahliye senaryosu",
            "gaps": "Bir çıkış yavaş kaldı",
            "result": "Genel başarı",
            "employee_ids": [],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["drill_type"] == "Yangın"
    assert body["status"] == "yapildi"
    drill_id = body["id"]

    listed = client.get("/api/v1/drills", headers=headers)
    assert listed.status_code == 200
    assert any(x["id"] == drill_id for x in listed.json())

    export = client.get(f"/api/v1/drills/{drill_id}/export.txt", headers=headers)
    assert export.status_code == 200
    assert "TATBİKAT" in export.text.upper() or "TATBIKAT" in export.text.upper()

    deleted = client.delete(f"/api/v1/drills/{drill_id}", headers=headers)
    assert deleted.status_code == 200
    listed2 = client.get("/api/v1/drills", headers=headers)
    assert all(x["id"] != drill_id for x in listed2.json())
