"""Eğitim katılımcıları: yalnızca seçilenler kaydedilir ve PDF'e girer.

Kullanıcı şikâyeti: personeli tek tek seçtiği hâlde çıktıda herkes listeleniyordu.
Bu testler kaydın seçimi birebir yansıttığını ve seçim değişince PATCH ile
güncellendiğini (yeni kopya kayıt açılmadan) doğrular.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "training_participants.db"
    url = f"sqlite:///{db_file.as_posix()}"
    upload = tmp_path / "uploads"
    upload.mkdir()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setenv("UPLOAD_DIR", str(upload))
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"
    settings.upload_dir = str(upload)
    settings.upload_gateway_enabled = False

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    import app.main as mainmod

    mainmod.engine = engine
    mainmod.SessionLocal = dbmod.SessionLocal
    ent.Base.metadata.create_all(bind=engine)

    test_client = TestClient(mainmod.app)
    try:
        yield test_client
    finally:
        test_client.close()
        engine.dispose()


def _seed(client: TestClient) -> tuple[dict, int, list[int]]:
    """OSGB + firma + 4 aktif çalışan + yönetici kullanıcı; token ve id'leri döner."""
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, Employee, OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Katilimci OSGB",
            authorization_number="YETKI-KT-1",
            tax_number="1234509876",
            responsible_manager="Yonetici",
            email="katilimci-osgb@test.com",
            phone="02120000000",
            address="Istanbul",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Katilimci AS",
            tax_number="9876501234",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
        employee_ids = []
        for i, name in enumerate(["Ali Veli", "Ayse Yilmaz", "Mehmet Kaya", "Zeynep Demir"], start=1):
            emp = Employee(
                company_id=company.id,
                full_name=name,
                national_id_masked=f"1000000000{i}",
                job_title="Operator",
                is_active=True,
            )
            db.add(emp)
            db.flush()
            employee_ids.append(emp.id)
        db.add(
            User(
                email="katilimci-admin@test.com",
                full_name="Katilimci Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                company_id=None,
                is_active=True,
            )
        )
        db.commit()
        company_id = company.id

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "katilimci-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, company_id, employee_ids


def _payload(company_id: int, participant_ids: list[int]) -> dict:
    start = date.today()
    return {
        "company_id": company_id,
        "title": "Temel Is Sagligi ve Guvenligi Egitimi",
        "training_type": "Temel İSG Eğitimi",
        "delivery_method": "Yüz yüze",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=1)).isoformat(),
        "hazard_class": "Tehlikeli",
        "sector": "nace_46_83_06",
        "instructor_name": "Egitmen Kisi",
        "attendance_verified": True,
        "success_verified": True,
        "participant_ids": participant_ids,
    }


def test_only_selected_employees_become_participants(client):
    headers, company_id, employee_ids = _seed(client)
    picked = [employee_ids[0], employee_ids[2]]

    created = client.post("/api/v1/trainings", headers=headers, json=_payload(company_id, picked))
    assert created.status_code == 200, created.text
    body = created.json()
    assert sorted(p["employee_id"] for p in body["participants"]) == sorted(picked)

    pdf = client.get(f"/api/v1/trainings/{body['id']}/attendance.pdf", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.content[:4] == b"%PDF"


def test_patch_replaces_participant_list_without_new_record(client):
    headers, company_id, employee_ids = _seed(client)
    created = client.post(
        "/api/v1/trainings",
        headers=headers,
        json=_payload(company_id, employee_ids),  # önce hepsi
    )
    assert created.status_code == 200, created.text
    training_id = created.json()["id"]
    assert len(created.json()["participants"]) == 4

    kept = [employee_ids[1], employee_ids[3]]
    patched = client.patch(
        f"/api/v1/trainings/{training_id}",
        headers=headers,
        json={"participant_ids": kept},
    )
    assert patched.status_code == 200, patched.text
    assert sorted(p["employee_id"] for p in patched.json()["participants"]) == sorted(kept)

    listed = client.get("/api/v1/trainings", headers=headers)
    assert listed.status_code == 200
    assert [t["id"] for t in listed.json()] == [training_id]  # kopya kayıt açılmadı


def test_patch_rejects_empty_or_foreign_participants(client):
    headers, company_id, employee_ids = _seed(client)
    training_id = client.post(
        "/api/v1/trainings", headers=headers, json=_payload(company_id, employee_ids[:2])
    ).json()["id"]

    empty = client.patch(
        f"/api/v1/trainings/{training_id}", headers=headers, json={"participant_ids": []}
    )
    assert empty.status_code == 422

    foreign = client.patch(
        f"/api/v1/trainings/{training_id}",
        headers=headers,
        json={"participant_ids": [max(employee_ids) + 999]},
    )
    assert foreign.status_code == 422


def test_completed_training_is_archived_instead_of_deleted(client):
    headers, company_id, employee_ids = _seed(client)
    created = client.post(
        "/api/v1/trainings",
        headers=headers,
        json=_payload(company_id, employee_ids[:2]),
    )
    assert created.status_code == 200, created.text
    training_id = created.json()["id"]

    completed = client.patch(
        f"/api/v1/trainings/{training_id}",
        headers=headers,
        json={
            "status": "completed",
            "attendance_verified": True,
            "success_verified": True,
        },
    )
    assert completed.status_code == 200, completed.text

    archived = client.post(
        f"/api/v1/trainings/{training_id}/archive",
        headers=headers,
        json={"reason": "Belge üretimi tamamlandı; tarihsel kayıt korundu."},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived_at"]
    assert archived.json()["archive_reason"]

    hidden = client.get("/api/v1/trainings", headers=headers)
    assert hidden.status_code == 200, hidden.text
    assert all(row["id"] != training_id for row in hidden.json())

    visible = client.get(
        "/api/v1/trainings?include_archived=true",
        headers=headers,
    )
    assert visible.status_code == 200, visible.text
    assert next(row for row in visible.json() if row["id"] == training_id)["archived_at"]

    deleted = client.delete(f"/api/v1/trainings/{training_id}", headers=headers)
    assert deleted.status_code == 409, deleted.text


def test_safety_specialist_can_create_and_complete_assigned_training_but_cannot_manage_package(client):
    admin_headers, company_id, employee_ids = _seed(client)
    created = client.post(
        "/api/v1/trainings",
        headers=admin_headers,
        json=_payload(company_id, employee_ids[:2]),
    )
    assert created.status_code == 200, created.text
    training_id = created.json()["id"]

    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        IsgProfessional,
        ProfessionalType,
        User,
        UserRole,
        WorkplaceAssignment,
    )

    with SessionLocal() as db:
        company = db.get(Company, company_id)
        professional = IsgProfessional(
            osgb_id=company.osgb_id,
            full_name="Rol Uzmanı",
            email="rol-uzmani@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            is_active=True,
        )
        db.add(professional)
        db.flush()
        db.add(
            WorkplaceAssignment(
                osgb_id=company.osgb_id,
                company_id=company_id,
                professional_id=professional.id,
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                start_date=date.today(),
                status=AssignmentStatus.ACTIVE,
            )
        )
        db.add(
            User(
                email="rol-uzmani@test.com",
                full_name="Rol Uzmanı",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.SAFETY_SPECIALIST,
                osgb_id=company.osgb_id,
                company_id=company_id,
                is_active=True,
            )
        )
        db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "rol-uzmani@test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    specialist_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    create_as_specialist = client.post(
        "/api/v1/trainings",
        headers=specialist_headers,
        json=_payload(company_id, employee_ids[:1]),
    )
    assert create_as_specialist.status_code == 200, create_as_specialist.text
    specialist_training = create_as_specialist.json()
    assert specialist_training["sector"] == "nace_46_83_06"
    assert specialist_training["hazard_class"] == "Tehlikeli"

    completed = client.patch(
        f"/api/v1/trainings/{training_id}",
        headers=specialist_headers,
        json={
            "status": "completed",
            "attendance_verified": True,
            "success_verified": True,
        },
    )
    assert completed.status_code == 200, completed.text

    rename_as_specialist = client.patch(
        f"/api/v1/trainings/{training_id}",
        headers=specialist_headers,
        json={"notes": "Paket tanımı değiştirilemez."},
    )
    assert rename_as_specialist.status_code == 403, rename_as_specialist.text

    deleted = client.delete(f"/api/v1/trainings/{training_id}", headers=specialist_headers)
    assert deleted.status_code == 403, deleted.text

    listed = client.get("/api/v1/trainings", headers=admin_headers)
    assert listed.status_code == 200
    assert any(row["id"] == training_id for row in listed.json())
