"""Ziyaret imza damgası."""
from __future__ import annotations

import base64
from datetime import date

import pytest
from fastapi.testclient import TestClient


def _tiny_png_data_url() -> str:
    # 1x1 PNG
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    # pad to pass min length check (64 bytes) — repeat
    padded = raw * 8
    return "data:image/png;base64," + base64.b64encode(padded).decode("ascii")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "visit_sig.db"
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


def _seed(client: TestClient) -> tuple[str, int]:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        ServiceVisit,
        User,
        UserRole,
        VisitStatus,
        WorkplaceAssignment,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Sig OSGB",
            authorization_number="S-001",
            tax_number="4445556667",
            responsible_manager="Yönetici",
            email="sig@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Sig İşyeri",
            sgk_registry_no="SGK-S01",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Saha Uzman",
            email="uzman@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
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
                start_date=date.today(),
                status=AssignmentStatus.ACTIVE,
            )
        )
        db.add(
            User(
                email="uzman@test.com",
                full_name="Saha Uzman",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.SAFETY_SPECIALIST,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        visit = ServiceVisit(
            osgb_id=osgb.id,
            company_id=company.id,
            professional_id=pro.id,
            visit_date=date.today(),
            subject="İmzalı ziyaret",
            duration_minutes=60,
            status=VisitStatus.PLANNED,
        )
        db.add(visit)
        db.commit()
        vid = visit.id

    r = client.post("/api/v1/auth/login", json={"email": "uzman@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], vid


def test_complete_with_signature(client):
    token, visit_id = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.patch(
        f"/api/v1/operations/visits/{visit_id}/complete",
        headers=headers,
        json={"signature_data_url": _tiny_png_data_url()},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["signature_captured_at"] is not None
    assert body["signature_file_name"]

    dl = client.get(f"/api/v1/operations/visits/{visit_id}/signature", headers=headers)
    assert dl.status_code == 200
    assert len(dl.content) >= 64
