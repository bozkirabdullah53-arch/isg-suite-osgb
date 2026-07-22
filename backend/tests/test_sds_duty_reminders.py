"""0.9.122 — SDS gözden geçirme: saha görev paneli + bildirim taraması."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.services.notifications import rebuild_company_notifications
from app.services.professional_duty import build_my_duty_board


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "sds_duty.db"
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
    from app.models.entities import (
        AssignmentStatus,
        ChemicalProduct,
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
            name="SDS Duty OSGB",
            authorization_number="YETKI-SDS-DUTY",
            tax_number="5566778899",
            responsible_manager="Yonetici",
            email="sds-duty-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="SDS Duty Firma",
            tax_number="4455667788",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
        user = User(
            email="sds-duty-uzman@test.com",
            full_name="SDS Duty Uzman",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.SAFETY_SPECIALIST,
            osgb_id=osgb.id,
            company_id=company.id,
            is_active=True,
        )
        db.add(user)
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="SDS Duty Uzman",
            email="sds-duty-uzman@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="UZM-SDS-DUTY",
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
                start_date=date.today() - timedelta(days=30),
                required_minutes_monthly=400,
                planned_minutes_monthly=400,
                actual_minutes_monthly=100,
            )
        )
        overdue = ChemicalProduct(
            company_id=company.id,
            product_name="Aseton",
            cas_number="67-64-1",
            has_sds_file=True,
            next_review_date=date.today() - timedelta(days=5),
            created_by_id=user.id,
            is_active=True,
        )
        soon = ChemicalProduct(
            company_id=company.id,
            product_name="Tiner",
            has_sds_file=False,
            next_review_date=date.today() + timedelta(days=7),
            created_by_id=user.id,
            is_active=True,
        )
        db.add_all([overdue, soon])
        db.commit()
        return {
            "company_id": company.id,
            "user_id": user.id,
            "email": user.email,
        }


def test_health_flags_sds_review_reminders(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.131"
    assert body["sds_review_reminders"] == "duty-notify-v1"
    assert body["osgb_mevzuat_link"] == "dashboard-v1"
    assert body["osgb_sds_due"] == "dashboard-v1"
    assert body["integration_readiness"] == "checklist-v1"
    assert body["risk_photo_tags"] == "checklist-v1"


def test_duty_board_includes_sds_review_alerts(client):
    seed = _seed(client)
    from app.core.database import SessionLocal
    from app.models.entities import User

    with SessionLocal() as db:
        user = db.get(User, seed["user_id"])
        board = build_my_duty_board(db, user)

    overdue = board["alerts"]["overdue"]
    due_soon = board["alerts"]["due_soon"]
    assert any(a.get("check_code") == "sds_review" and "Aseton" in a.get("title", "") for a in overdue)
    assert any(a.get("check_code") == "sds_review" and "Tiner" in a.get("title", "") for a in due_soon)
    sds_overdue = next(a for a in overdue if a.get("check_code") == "sds_review")
    assert sds_overdue["module"] == "sds"
    assert sds_overdue["module_label"] == "SDS / PKD"


def test_notifications_include_sds_review(client):
    seed = _seed(client)
    from app.core.database import SessionLocal
    from app.models.entities import Notification, NotificationType
    from sqlalchemy import select

    with SessionLocal() as db:
        n = rebuild_company_notifications(db, seed["company_id"])
        assert n >= 2
        rows = list(
            db.scalars(
                select(Notification).where(Notification.entity_type == "chemical_product")
            ).all()
        )
        assert len(rows) >= 2
        titles = " ".join(r.title for r in rows)
        assert "SDS gözden geçirme" in titles
        assert any(r.type == NotificationType.CRITICAL for r in rows)
        assert any(r.type == NotificationType.WARNING for r in rows)
