"""GPS'li görsel saha denetimi için izole API/regresyon kontrolleri."""
from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture()
def visual_client(tmp_path, monkeypatch):
    db_file = tmp_path / "visual-field.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "visual-field-test-secret-at-least-32-chars")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.core.database as dbmod
    from app.core.config import settings
    from app.models.entities import Base

    settings.database_url = url
    settings.secret_key = "visual-field-test-secret-at-least-32-chars"
    settings.environment = "development"
    settings.upload_dir = str(tmp_path / "uploads")
    settings.field_ai_enabled = False
    settings.field_ai_data_processing_allowed = False
    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed(client: TestClient) -> tuple[dict[str, str], dict[str, int]]:
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
        osgb = OsgbOrganization(name="Görsel OSGB", authorization_number="VIS-1", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Görsel İşyeri", osgb_id=osgb.id, is_active=True, nace_code="10.10")
        other = Company(name="Başka İşyeri", osgb_id=osgb.id, is_active=True)
        db.add_all([company, other])
        db.flush()
        professional = IsgProfessional(osgb_id=osgb.id, full_name="Görsel Uzman", email="visual@test.com", professional_type=ProfessionalType.SAFETY_SPECIALIST, is_active=True)
        db.add(professional)
        db.flush()
        db.add(WorkplaceAssignment(osgb_id=osgb.id, company_id=company.id, professional_id=professional.id, professional_type=ProfessionalType.SAFETY_SPECIALIST, start_date=date.today(), status=AssignmentStatus.ACTIVE))
        user = User(email="visual@test.com", full_name="Görsel Uzman", hashed_password=get_password_hash("VisualPass123!"), role=UserRole.SAFETY_SPECIALIST, osgb_id=osgb.id, is_active=True)
        employee = Employee(company_id=company.id, full_name="Sorumlu Çalışan", is_active=True)
        db.add_all([user, employee])
        db.commit()
        ids = {"company_id": company.id, "other_company_id": other.id, "employee_id": employee.id}

    login = client.post("/api/v1/auth/login", json={"email": "visual@test.com", "password": "VisualPass123!"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, ids


def _jpeg() -> bytes:
    out = BytesIO()
    Image.new("RGB", (160, 100), "#0f766e").save(out, format="JPEG")
    return out.getvalue()


def test_visual_field_end_to_end_and_safe_ai_failure(visual_client):
    headers, ids = _seed(visual_client)
    catalog = visual_client.get(f"/api/v1/field-inspections/catalog?company_id={ids['company_id']}", headers=headers)
    assert catalog.status_code == 200, catalog.text
    assert len(catalog.json()["categories"]) == 75

    site = visual_client.post("/api/v1/field-inspections/sites", headers=headers, json={"company_id": ids["company_id"], "name": "Ana Saha"})
    assert site.status_code == 200, site.text
    site_id = site.json()["item"]["id"]
    area = visual_client.post("/api/v1/field-inspections/areas", headers=headers, json={"company_id": ids["company_id"], "site_id": site_id, "name": "Üretim Alanı"})
    assert area.status_code == 200, area.text
    area_id = area.json()["item"]["id"]
    inspection = visual_client.post("/api/v1/field-inspections", headers=headers, json={"company_id": ids["company_id"], "site_id": site_id, "area_id": area_id, "gps_status": "not_available", "manual_location_note": "İç mekân"})
    assert inspection.status_code == 200, inspection.text
    inspection_id = inspection.json()["id"]

    photo = visual_client.post(f"/api/v1/field-inspections/{inspection_id}/photos", headers=headers, files={"file": ("kanıt.jpg", _jpeg(), "image/jpeg")}, data={"gps_status": "not_available", "client_reference": "photo-1", "privacy_blur": "true"})
    assert photo.status_code == 200, photo.text
    photo_id = photo.json()["id"]
    assert photo.json()["edit_meta"]["privacy_blur"] is True
    assert photo.json()["location"]["area"]["id"] == area_id
    original = visual_client.get(f"/api/v1/field-inspections/{inspection_id}/photos/{photo_id}/original", headers=headers)
    marked = visual_client.get(f"/api/v1/field-inspections/{inspection_id}/photos/{photo_id}/marked", headers=headers)
    assert original.status_code == marked.status_code == 200
    assert original.content != b""

    analysis = visual_client.post(f"/api/v1/field-inspections/{inspection_id}/analyze", headers=headers)
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()["inspection"]["ai_status"] == "failed"
    assert "Bulgular oluşturulmadı" in analysis.json()["inspection"]["ai_error"]

    finding = visual_client.post(f"/api/v1/field-inspections/{inspection_id}/findings", headers=headers, json={"hazard_name": "Açık kablo", "visual_evidence": "Fotoğrafta açık kablo görülüyor.", "nonconformity_description": "Kablo korumasız durumda.", "suggested_priority": "high"})
    assert finding.status_code == 200, finding.text
    finding_id = finding.json()["id"]
    annotation = visual_client.post(f"/api/v1/field-inspections/{inspection_id}/photos/{photo_id}/annotations", headers=headers, json={"photo_id": photo_id, "finding_id": finding_id, "shape_type": "rectangle", "x": 0.1, "y": 0.1, "width": 0.4, "height": 0.3, "label": "1"})
    assert annotation.status_code == 200, annotation.text
    moved = visual_client.patch(f"/api/v1/field-inspections/{inspection_id}/annotations/{annotation.json()['id']}", headers=headers, json={"x": 0.2, "y": 0.2, "width": 0.35, "height": 0.25})
    assert moved.status_code == 200, moved.text
    legal = visual_client.put(f"/api/v1/field-inspections/{inspection_id}/findings/{finding_id}/legal-references", headers=headers, json={"references": [{"regulation_name": "6331 sayılı İş Sağlığı ve Güvenliği Kanunu", "article": "5", "relation_explanation": "İSG önleme ilkeleri", "verification_status": "verified"}]})
    assert legal.status_code == 200, legal.text
    action = visual_client.post(f"/api/v1/field-inspections/{inspection_id}/findings/{finding_id}/actions", headers=headers, json={"finding_id": finding_id, "title": "Kabloyu koru", "activity": "Kabloyu uygun kanala al.", "responsible_employee_id": ids["employee_id"], "term_date": "2099-01-01", "priority": "high"})
    assert action.status_code == 200, action.text
    completed_action = visual_client.post(f"/api/v1/field-inspections/{inspection_id}/actions/{action.json()['id']}/complete", headers=headers)
    assert completed_action.status_code == 200, completed_action.text
    blocked = visual_client.post(f"/api/v1/field-inspections/{inspection_id}/approve", headers=headers, json={})
    assert blocked.status_code == 409
    reviewed = visual_client.patch(f"/api/v1/field-inspections/{inspection_id}/findings/{finding_id}", headers=headers, json={"status": "accepted"})
    assert reviewed.status_code == 200, reviewed.text
    approved = visual_client.post(f"/api/v1/field-inspections/{inspection_id}/approve", headers=headers, json={})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    pdf = visual_client.get(f"/api/v1/field-inspections/{inspection_id}/report.pdf", headers=headers)
    xlsx = visual_client.get(f"/api/v1/field-inspections/{inspection_id}/report.xlsx", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"


def test_visual_field_tenant_boundary(visual_client):
    headers, ids = _seed(visual_client)
    forbidden = visual_client.get(f"/api/v1/field-inspections/catalog?company_id={ids['other_company_id']}", headers=headers)
    assert forbidden.status_code == 403
