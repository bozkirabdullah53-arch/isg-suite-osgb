"""İSG uzmanının firma kartı düzenleme kapsamı."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def specialist_client(tmp_path, monkeypatch):
    db_file = tmp_path / "company-update-specialist.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "company-update-specialist-secret-key-at-least-32-chars")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "company-update-specialist-secret-key-at-least-32-chars"
    settings.environment = "development"

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

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

    password = "TestPass123!"
    with dbmod.SessionLocal() as db:
        osgb = OsgbOrganization(name="Uzman Yetki OSGB", is_active=True)
        other_osgb = OsgbOrganization(name="Diğer OSGB", is_active=True)
        db.add_all([osgb, other_osgb])
        db.flush()

        assigned = Company(
            name="Atanmış İşyeri",
            osgb_id=osgb.id,
            sgk_registry_no="SGK-UZMAN-1",
            is_active=True,
        )
        unassigned = Company(
            name="Atanmamış İşyeri",
            osgb_id=osgb.id,
            sgk_registry_no="SGK-UZMAN-2",
            is_active=True,
        )
        other_tenant = Company(
            name="Diğer OSGB İşyeri",
            osgb_id=other_osgb.id,
            sgk_registry_no="SGK-UZMAN-3",
            is_active=True,
        )
        db.add_all([assigned, unassigned, other_tenant])
        db.flush()

        specialist = User(
            email="atanmis.uzman@example.com",
            full_name="Atanmış Uzman",
            hashed_password=get_password_hash(password),
            role=UserRole.SAFETY_SPECIALIST,
            osgb_id=osgb.id,
            is_active=True,
        )
        professional = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Atanmış Uzman",
            email=specialist.email,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="A-UZMAN-1",
            is_active=True,
        )
        db.add_all([specialist, professional])
        db.flush()
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=assigned.id,
                professional_id=professional.id,
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                start_date=date.today(),
                status=AssignmentStatus.ACTIVE,
            )
        )
        db.commit()

        seed = {
            "email": specialist.email,
            "password": password,
            "assigned_id": assigned.id,
            "unassigned_id": unassigned.id,
            "other_tenant_id": other_tenant.id,
            "osgb_id": osgb.id,
        }

    from app.main import app

    return TestClient(app), seed


def _token(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_assigned_safety_specialist_can_edit_only_workplace_card(specialist_client):
    client, seed = specialist_client
    headers = {
        "Authorization": f"Bearer {_token(client, seed['email'], seed['password'])}"
    }

    listed = client.get("/api/v1/companies", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [row["id"] for row in listed.json()] == [seed["assigned_id"]]

    updated = client.put(
        f"/api/v1/companies/{seed['assigned_id']}",
        headers=headers,
        json={
            "name": "Atanmış İşyeri Güncellendi",
            "sgk_registry_no": "SGK-UZMAN-GUNCEL",
            "nace_code": "46.83.06",
            "hazard_class": "Tehlikeli",
            "address": "Güncel işyeri adresi, Ankara",
            "phone": "03121234567",
            "authorized_person": "Ayşe Yılmaz",
            # Uzman, tenant veya aktiflik durumunu değiştiremez.
            "osgb_id": seed["osgb_id"] + 1,
            "is_active": False,
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["name"] == "Atanmış İşyeri Güncellendi"
    assert body["sgk_registry_no"] == "SGK-UZMAN-GUNCEL"
    assert body["nace_code"] == "46.83.06"
    assert body["is_active"] is True
    assert body["osgb_id"] == seed["osgb_id"]

    assert client.put(
        f"/api/v1/companies/{seed['unassigned_id']}",
        headers=headers,
        json={"authorized_person": "Yetkisiz Değişiklik"},
    ).status_code == 403
    assert client.put(
        f"/api/v1/companies/{seed['other_tenant_id']}",
        headers=headers,
        json={"authorized_person": "Çapraz OSGB Denemesi"},
    ).status_code == 403
