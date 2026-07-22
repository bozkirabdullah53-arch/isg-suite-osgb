"""0.9.134 — Acil durum ekipleri (emergency teams) smoke tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "emg.db"
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
    from app.models.entities import Company, Employee, OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Acil OSGB",
            authorization_number="YETKI-ACIL-1",
            tax_number="1112223334",
            responsible_manager="Acil Yonetici",
            email="acil-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()

        company = Company(
            name="Acil Firma",
            osgb_id=osgb.id,
            tax_number="1234567890",
            sgk_registry_no="1234567890123",
            hazard_class="Tehlikeli",
            address="Ankara",
            is_active=True,
        )
        db.add(company)
        # İzolasyon testi için ikinci firma
        other = Company(name="Diger Firma", osgb_id=osgb.id, is_active=True)
        db.add(other)
        db.flush()

        emps = []
        for i in range(4):
            e = Employee(
                company_id=company.id,
                full_name=f"Personel {i + 1}",
                job_title="Operatör",
                department="Üretim",
                is_active=True,
            )
            db.add(e)
            emps.append(e)
        other_emp = Employee(company_id=other.id, full_name="Diger Personel", is_active=True)
        db.add(other_emp)

        db.add(
            User(
                email="acil-uzman@test.com",
                full_name="Acil Uzman",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.SAFETY_SPECIALIST,
                osgb_id=osgb.id,
                company_id=company.id,
                is_active=True,
            )
        )
        db.commit()
        db.refresh(company)
        db.refresh(other)
        emp_ids = [e.id for e in db.query(Employee).filter(Employee.company_id == company.id).all()]

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "acil-uzman@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return {
        "token": r.json()["access_token"],
        "company_id": company.id,
        "other_company_id": other.id,
        "employee_ids": emp_ids,
    }


def test_health_acil_ekipler_flag(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.139"
    assert body["acil_ekipler"] == "emergency-teams-v1"


def test_overview_seeds_default_teams(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    r = client.get(f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # 6 varsayılan ekip otomatik oluşur
    assert body["kpis"]["team_count"] == 6
    assert body["company"]["sgk_registry_no"] == "1234567890123"
    assert body["can_edit"] is True
    codes = {t["type_code"] for t in body["teams"]}
    assert "sondurme" in codes and "ilk_yardim" in codes


def test_create_team_assign_list_soft_delete(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}

    # meta -> tür id
    meta = client.get("/api/v1/emergency-teams/meta", headers=headers).json()
    type_id = meta["team_types"][0]["id"]

    created = client.post(
        "/api/v1/emergency-teams/teams",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "type_id": type_id,
            "name": "Özel Söndürme Ekibi",
            "min_members": 3,
        },
    )
    assert created.status_code == 200, created.text
    team_id = created.json()["id"]

    # üye ata
    assigned = client.post(
        "/api/v1/emergency-teams/assignments",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "team_id": team_id,
            "employee_id": seed["employee_ids"][0],
            "membership": "asil",
            "is_leader": True,
            "role_title": "Ekip Başı",
        },
    )
    assert assigned.status_code == 200, assigned.text
    assignment_id = assigned.json()["id"]
    assert assigned.json()["cert_status"] == "grey"  # eğitim yok

    listed = client.get(
        f"/api/v1/emergency-teams/assignments?company_id={seed['company_id']}&team_id={team_id}",
        headers=headers,
    )
    assert listed.status_code == 200
    assert any(a["id"] == assignment_id for a in listed.json())

    # aynı personel ikinci kez -> 409
    dup = client.post(
        "/api/v1/emergency-teams/assignments",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "team_id": team_id,
            "employee_id": seed["employee_ids"][0],
        },
    )
    assert dup.status_code == 409

    # soft delete üye
    d = client.delete(f"/api/v1/emergency-teams/assignments/{assignment_id}", headers=headers)
    assert d.status_code == 200
    listed2 = client.get(
        f"/api/v1/emergency-teams/assignments?company_id={seed['company_id']}&team_id={team_id}",
        headers=headers,
    )
    assert all(a["id"] != assignment_id for a in listed2.json())

    # soft delete ekip
    dt = client.delete(f"/api/v1/emergency-teams/teams/{team_id}", headers=headers)
    assert dt.status_code == 200
    teams = client.get(f"/api/v1/emergency-teams/teams?company_id={seed['company_id']}", headers=headers)
    assert all(t["id"] != team_id for t in teams.json())


def test_cert_status_yellow_after_training(client):
    from datetime import date, timedelta

    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    meta = client.get("/api/v1/emergency-teams/meta", headers=headers).json()
    type_id = meta["team_types"][0]["id"]
    team_id = client.post(
        "/api/v1/emergency-teams/teams",
        headers=headers,
        json={"company_id": seed["company_id"], "type_id": type_id, "name": "İlk Yardım"},
    ).json()["id"]
    a_id = client.post(
        "/api/v1/emergency-teams/assignments",
        headers=headers,
        json={"company_id": seed["company_id"], "team_id": team_id, "employee_id": seed["employee_ids"][1]},
    ).json()["id"]

    soon = (date.today() + timedelta(days=10)).isoformat()
    tr = client.post(
        f"/api/v1/emergency-teams/assignments/{a_id}/trainings",
        headers=headers,
        json={"training_type": "İlk Yardım", "valid_until": soon},
    )
    assert tr.status_code == 200, tr.text

    lst = client.get(
        f"/api/v1/emergency-teams/assignments?company_id={seed['company_id']}&team_id={team_id}",
        headers=headers,
    ).json()
    row = next(a for a in lst if a["id"] == a_id)
    assert row["cert_status"] == "yellow"


def test_company_isolation(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    # Uzmanın erişemeyeceği başka firma (görevlendirme yok, company_id farklı)
    r = client.get(
        f"/api/v1/emergency-teams/overview?company_id={seed['other_company_id']}",
        headers=headers,
    )
    assert r.status_code == 403


def test_export_xlsx_and_pdf(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    # overview varsayılan ekipleri kurar
    client.get(f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}", headers=headers)

    x = client.get(f"/api/v1/emergency-teams/export.xlsx?company_id={seed['company_id']}", headers=headers)
    assert x.status_code == 200
    assert len(x.content) > 100

    p = client.get(f"/api/v1/emergency-teams/export.pdf?company_id={seed['company_id']}", headers=headers)
    assert p.status_code == 200
    assert p.content[:4] == b"%PDF"
