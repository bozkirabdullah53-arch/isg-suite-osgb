"""0.9.121 — Risk fotoğrafı tehlike etiketi checklist (checklist-v1)."""
from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.services.risk_photo_tags import TAGS_ENGINE, parse_tags, serialize_selected


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "risk_photo_tags.db"
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
        Hazard,
        HazardCategory,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        RiskAssessment,
        User,
        UserRole,
        WorkplaceAssignment,
    )
    from app.services.risk_scoring import evaluate

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Photo OSGB",
            authorization_number="YETKI-PHOTO-1",
            tax_number="1122334455",
            responsible_manager="Yonetici",
            email="photo-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Photo Firma A.S.",
            tax_number="9988776655",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
        user = User(
            email="photo-uzman@test.com",
            full_name="Photo Uzman",
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
            full_name="Photo Uzman",
            email="photo-uzman@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="UZM-PHOTO-1",
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
        cat = HazardCategory(name="Test Kategori", icon="test", sort_order=1)
        db.add(cat)
        db.flush()
        hazard = Hazard(
            category_id=cat.id,
            code="TST-001",
            name="Test Tehlike",
            is_active=True,
        )
        db.add(hazard)
        db.flush()
        scored = evaluate(3, 3)
        risk = RiskAssessment(
            risk_code="RSK-PHOTO-1",
            company_id=company.id,
            hazard_id=hazard.id,
            department_name="Uretim",
            activity="Kaynak",
            risk_definition="Kaygan zemin ve elektrik",
            probability=3,
            severity=3,
            risk_score=scored["risk_score"],
            risk_level=scored["risk_level"],
            term_days=scored.get("term_days"),
            term_suggested=scored.get("term_suggested"),
            term_overridden=False,
            status="Açık",
            created_by_id=user.id,
        )
        db.add(risk)
        db.commit()
        risk_id = risk.id

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "photo-uzman@test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return token, risk_id


def test_parse_serialize_roundtrip():
    raw = serialize_selected(["ppe_missing", "electrical", "bogus"])
    body = parse_tags(raw)
    assert body["engine"] == TAGS_ENGINE
    assert body["selected"] == ["ppe_missing", "electrical"]
    assert "PPE / KKD eksik" in body["labels"]


def test_health_flag_risk_photo_tags(release_flags):
    body = release_flags
    assert body.get("version")
    assert body["risk_photo_tags"] == "checklist-v1"
    assert body["ghs_label_checklist"] == "ghs-label-checklist-v1"


def test_photo_tag_catalog(client):
    token, _ = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/risks/photo-tag-catalog", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "checklist-v1"
    codes = {i["code"] for i in body["items"]}
    assert "ppe_missing" in codes
    assert "slippery_floor" in codes
    assert "work_at_height" in codes


def test_upload_media_with_tags(client):
    token, risk_id = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    up = client.post(
        f"/api/v1/risks/{risk_id}/media",
        headers=headers,
        files={"file": ("scene.png", io.BytesIO(png), "image/png")},
        data={
            "tags": '["ppe_missing","slippery_floor"]',
            "client_reference": "media-photo-test-1",
            "captured_at": "2026-08-20T10:15:00+03:00",
            "gps_lat": "41.123456",
            "gps_lng": "29.123456",
            "gps_accuracy_m": "7.5",
        },
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["tags"] == ["ppe_missing", "slippery_floor"]
    assert "PPE / KKD eksik" in body["tag_labels"]
    assert body["client_reference"] == "media-photo-test-1"
    assert body["captured_at"].startswith("2026-08-20T07:15:00")
    assert body["gps_lat"] == 41.123456
    assert body["gps_lng"] == 29.123456
    assert body["gps_accuracy_m"] == 7.5

    retry = client.post(
        f"/api/v1/risks/{risk_id}/media",
        headers=headers,
        files={"file": ("different.png", io.BytesIO(png), "image/png")},
        data={"client_reference": "media-photo-test-1"},
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == body["id"]

    put = client.put(
        f"/api/v1/risks/{risk_id}/media/{body['id']}/tags",
        headers=headers,
        json={"selected": ["electrical", "work_at_height"]},
    )
    assert put.status_code == 200, put.text
    assert put.json()["tags"] == ["electrical", "work_at_height"]


def test_field_inspection_risk_and_dof_are_idempotent(client):
    token, risk_id = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = client.get(f"/api/v1/risks/{risk_id}", headers=headers)
    assert base.status_code == 200, base.text
    source = base.json()
    payload = {
        "company_id": source["company_id"],
        "department_name": "Saha Denetimi",
        "hazard_id": source["hazard_id"],
        "method_code": "5x5_l",
        "record_origin": "field_inspection",
        "client_reference": "field-risk-client-1",
        "observed_at": "2026-08-20T10:15:00+03:00",
        "observation_location": "Pres önü",
        "gps_lat": 41.123456,
        "gps_lng": 29.123456,
        "gps_accuracy_m": 7.5,
        "activity": "Saha denetimi — Pres önü",
        "risk_definition": "Makine koruyucusu eksik.",
        "affected_group": "Çalışan",
        "probability": 3,
        "severity": 4,
        "status": "Açık",
    }
    created = client.post("/api/v1/risks", headers=headers, json=payload)
    assert created.status_code == 200, created.text
    row = created.json()
    assert row["record_origin"] == "field_inspection"
    assert row["client_reference"] == "field-risk-client-1"
    assert row["observation_location"] == "Pres önü"
    assert row["gps_accuracy_m"] == 7.5

    retry = client.post("/api/v1/risks", headers=headers, json=payload)
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == row["id"]

    dof_payload = {
        "description": "Makine koruyucusu takılacak.",
        "responsible_person": "Sorumlu",
        "term_date": "2026-08-30",
        "client_reference": "field-dof-client-1",
    }
    dof = client.post(f"/api/v1/risks/{row['id']}/dofs", headers=headers, json=dof_payload)
    assert dof.status_code == 200, dof.text
    dof_row = dof.json()
    assert dof_row["client_reference"] == "field-dof-client-1"
    dof_retry = client.post(f"/api/v1/risks/{row['id']}/dofs", headers=headers, json=dof_payload)
    assert dof_retry.status_code == 200, dof_retry.text
    assert dof_retry.json()["id"] == dof_row["id"]


def test_photo_pdf_reports_embed_saved_and_draft_photos(client):
    token, risk_id = _seed(client)
    headers = {"Authorization": f"Bearer {token}"}
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    upload = client.post(
        f"/api/v1/risks/{risk_id}/media",
        headers=headers,
        files={"file": ("saved.png", io.BytesIO(png), "image/png")},
        data={"captured_at": "2026-08-20T10:15:00+03:00"},
    )
    assert upload.status_code == 200, upload.text

    saved_report = client.get(f"/api/v1/risks/{risk_id}/report.pdf", headers=headers)
    assert saved_report.status_code == 200, saved_report.text
    assert saved_report.content.startswith(b"%PDF")
    assert b"/Subtype /Image" in saved_report.content

    risk_body = client.get(f"/api/v1/risks/{risk_id}", headers=headers).json()

    draft_report = client.post(
        "/api/v1/risks/field-report.pdf",
        headers=headers,
        files={"files": ("draft.png", io.BytesIO(png), "image/png")},
        data={
            "company_id": str(risk_body["company_id"]),
            "department_name": "Saha",
            "location": "Pres önü",
            "summary": "Fotoğraflı saha bulgusu",
            "probability": "3",
            "severity": "4",
            "photo_meta": '[{"name":"draft.png","tags":["work_at_height"]}]',
            "vision_results": '[{"summary":"Kontrol gerekli.","hazards":[{"category":"Düşme","observed":"Açık kenar","confidence":"bozuk"}]}]',
        },
    )
    assert draft_report.status_code == 200, draft_report.text
    assert draft_report.content.startswith(b"%PDF")
    assert b"/Subtype /Image" in draft_report.content
