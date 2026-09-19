"""Uzman odası P1 kapsamı: görev, rapor, mevzuat ve bildirim izolasyonu."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def client(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'specialist_room.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    import app.core.database as dbmod
    import app.models.entities as ent
    import app.models.training_nace  # noqa: F401
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "production"
    settings.upload_dir = str(tmp_path / "uploads")

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    import app.main as main_mod
    # Test koleksiyonu app.main'i daha önce import etmiş olabilir; lifespan'ın
    # tuttuğu engine/session referanslarını bu izole veritabanına bağla.
    main_mod.engine = engine
    main_mod.SessionLocal = dbmod.SessionLocal

    return TestClient(main_mod.app)


def _seed():
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        Employee,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        User,
        UserRole,
        WorkplaceAssignment,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Uzman Odası OSGB", is_active=True)
        other_osgb = OsgbOrganization(name="Başka OSGB", is_active=True)
        db.add_all([osgb, other_osgb])
        db.flush()
        company_a = Company(
            name="Uzman Firma A",
            nace_code="46.83.06",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        company_b = Company(
            name="Uzman Firma B",
            nace_code="41.20.01",
            hazard_class="Az Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        company_foreign = Company(
            name="Başka Kapsam Firma",
            nace_code="10.11.01",
            hazard_class="Tehlikeli",
            osgb_id=other_osgb.id,
            is_active=True,
        )
        db.add_all([company_a, company_b, company_foreign])
        db.flush()
        user = User(
            email="uzman-p1@test.com",
            full_name="P1 Uzman",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.SAFETY_SPECIALIST,
            osgb_id=osgb.id,
            is_active=True,
        )
        osgb_admin = User(
            email="osgb-admin-p1@test.com",
            full_name="P1 OSGB Yöneticisi",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            is_active=True,
        )
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="P1 Uzman",
            email="uzman-p1@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="P1-UZM-1",
            is_active=True,
        )
        db.add_all([user, osgb_admin, pro])
        db.flush()
        db.add_all(
            [
                Employee(company_id=company_a.id, full_name="A Çalışan", is_active=True),
                Employee(company_id=company_b.id, full_name="B Çalışan", is_active=True),
                WorkplaceAssignment(
                    osgb_id=osgb.id,
                    company_id=company_a.id,
                    professional_id=pro.id,
                    professional_type=ProfessionalType.SAFETY_SPECIALIST,
                    start_date=date.today(),
                    status=AssignmentStatus.ACTIVE,
                ),
                WorkplaceAssignment(
                    osgb_id=osgb.id,
                    company_id=company_b.id,
                    professional_id=pro.id,
                    professional_type=ProfessionalType.SAFETY_SPECIALIST,
                    start_date=date.today(),
                    status=AssignmentStatus.ACTIVE,
                ),
            ]
        )
        db.commit()
        return {
            "user_id": user.id,
            "admin_email": osgb_admin.email,
            "company_a": company_a.id,
            "company_b": company_b.id,
            "company_foreign": company_foreign.id,
        }


def _headers(client: TestClient, email: str = "uzman-p1@test.com"):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TestPass123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_specialist_board_and_report_are_assigned_scope_only(client):
    seed = _seed()
    headers = _headers(client)

    board = client.get("/api/v1/dashboard/my-duties", headers=headers)
    assert board.status_code == 200, board.text
    body = board.json()
    assert body["workplace_ids"] == [seed["company_a"], seed["company_b"]]
    assert {row["code"] for row in body["check_catalog"]} >= {
        "training_compliance",
        "ppe_register",
        "emergency_plan",
    }
    assert any(item["module"] == "specialist_reports" for item in body["quick_actions"])
    assert all("health" not in str(item).lower() for item in body["alerts"]["all"])

    report = client.get("/api/v1/reports/specialist-summary", headers=headers)
    assert report.status_code == 200, report.text
    report_body = report.json()
    assert {row["company_id"] for row in report_body["companies"]} == {
        seed["company_a"],
        seed["company_b"],
    }
    assert "health_record_count" not in report_body.get("totals", {})
    assert "health_record_count" not in report_body

    blocked = client.get(
        f"/api/v1/reports/specialist-summary?company_id={seed['company_foreign']}",
        headers=headers,
    )
    assert blocked.status_code == 403, blocked.text


def test_specialist_notifications_hide_clinical_and_foreign_company_rows(client):
    seed = _seed()
    headers = _headers(client)
    from app.core.database import SessionLocal
    from app.models.entities import Notification, NotificationType

    with SessionLocal() as db:
        db.add_all(
            [
                Notification(
                    company_id=seed["company_a"],
                    type=NotificationType.WARNING,
                    title="Güvenli uzman uyarısı",
                    message="Risk aksiyonu gerekli.",
                    entity_type="specialist_duty",
                    entity_id="risk_dof:1:",
                ),
                Notification(
                    company_id=seed["company_b"],
                    type=NotificationType.WARNING,
                    title="İkinci firma uyarısı",
                    message="İkinci firmada gözden geçirme gerekli.",
                    entity_type="specialist_duty",
                    entity_id="risk_dof:3:",
                ),
                Notification(
                    company_id=seed["company_a"],
                    type=NotificationType.CRITICAL,
                    title="Klinik kayıt",
                    message="Bu içerik uzmana görünmemeli.",
                    entity_type="health_record",
                    entity_id="99",
                ),
                Notification(
                    company_id=seed["company_foreign"],
                    type=NotificationType.WARNING,
                    title="Başka firma",
                    message="Kapsam dışı.",
                    entity_type="specialist_duty",
                    entity_id="risk_dof:2:",
                ),
            ]
        )
        db.commit()
        clinical_id = db.scalar(
            select(Notification.id).where(Notification.entity_type == "health_record")
        )

    rows = client.get("/api/v1/notifications", headers=headers)
    assert rows.status_code == 200, rows.text
    titles = {row["title"] for row in rows.json()}
    assert "Güvenli uzman uyarısı" in titles
    assert "Klinik kayıt" not in titles
    assert "Başka firma" not in titles

    company_a_rows = client.get(
        "/api/v1/notifications",
        params={"company_id": seed["company_a"]},
        headers=headers,
    )
    assert company_a_rows.status_code == 200, company_a_rows.text
    assert {row["title"] for row in company_a_rows.json()} == {"Güvenli uzman uyarısı"}

    company_b_rows = client.get(
        "/api/v1/notifications",
        params={"company_id": seed["company_b"]},
        headers=headers,
    )
    assert company_b_rows.status_code == 200, company_b_rows.text
    assert {row["title"] for row in company_b_rows.json()} == {"İkinci firma uyarısı"}

    foreign = client.get(
        "/api/v1/notifications",
        params={"company_id": seed["company_foreign"]},
        headers=headers,
    )
    assert foreign.status_code == 403, foreign.text

    forbidden = client.patch(f"/api/v1/notifications/{clinical_id}/read", headers=headers)
    assert forbidden.status_code == 403, forbidden.text


def test_specialist_can_read_curated_mevzuat_panel(client):
    _seed()
    headers = _headers(client)
    response = client.get("/api/v1/osgb/mevzuat-panel", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["catalog_total"] > 0


def test_osgb_admin_notification_filter_returns_selected_company_only(client):
    seed = _seed()
    headers = _headers(client, seed["admin_email"])
    from app.core.database import SessionLocal
    from app.models.entities import Notification, NotificationType

    with SessionLocal() as db:
        db.add_all(
            [
                Notification(
                    company_id=seed["company_a"],
                    type=NotificationType.WARNING,
                    title="OSGB Firma A bildirimi",
                    message="Firma A için kontrol gerekli.",
                ),
                Notification(
                    company_id=seed["company_b"],
                    type=NotificationType.WARNING,
                    title="OSGB Firma B bildirimi",
                    message="Firma B için kontrol gerekli.",
                ),
            ]
        )
        db.commit()

    selected_a = client.get(
        "/api/v1/notifications",
        params={"company_id": seed["company_a"]},
        headers=headers,
    )
    assert selected_a.status_code == 200, selected_a.text
    assert {row["title"] for row in selected_a.json()} == {"OSGB Firma A bildirimi"}

    selected_b = client.get(
        "/api/v1/notifications",
        params={"company_id": seed["company_b"]},
        headers=headers,
    )
    assert selected_b.status_code == 200, selected_b.text
    assert {row["title"] for row in selected_b.json()} == {"OSGB Firma B bildirimi"}

    outside_scope = client.get(
        "/api/v1/notifications",
        params={"company_id": seed["company_foreign"]},
        headers=headers,
    )
    assert outside_scope.status_code == 403, outside_scope.text
