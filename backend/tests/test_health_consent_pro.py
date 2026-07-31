"""Sağlık gözetimi Pro kuralları: aydınlatılmış onam, çift kayıt, kısıt gizliliği.

KVKK md.6 gereği özel nitelikli kişisel veri (sağlık) işlemek açık rızaya bağlı;
bu yüzden muayene kaydı onam işaretlenmeden açılamaz. OSGB merkez yöneticisi
(company_admin) klinik kayıtlara erişemez — yalnız hekim/DSP ve EİSA yöneticisi.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "health_consent.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"
    settings.upload_dir = str(tmp_path / "uploads")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.core.database as dbmod
    import app.models.entities as ent

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    ent.Base.metadata.create_all(bind=engine)

    from app.core.security import get_password_hash
    from app.models.entities import Company, Employee, OsgbOrganization, User, UserRole
    from app.main import app

    with dbmod.SessionLocal() as db:
        osgb = OsgbOrganization(name="Onam OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(
            name="Onam Firma",
            hazard_class="Tehlikeli",
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
        db.add_all(
            [
                User(
                    email="onam-hekim@test.com",
                    full_name="Hekim Kisi",
                    hashed_password=get_password_hash("HekimPass123!"),
                    role=UserRole.WORKPLACE_PHYSICIAN,
                    company_id=company.id,
                    is_active=True,
                ),
                User(
                    email="onam-dsp@test.com",
                    full_name="DSP Kisi",
                    hashed_password=get_password_hash("DspPass12345!"),
                    role=UserRole.OTHER_HEALTH_PERSONNEL,
                    company_id=company.id,
                    is_active=True,
                ),
                User(
                    email="onam-osgb@test.com",
                    full_name="OSGB Yonetici",
                    hashed_password=get_password_hash("OsgbPass123!"),
                    role=UserRole.COMPANY_ADMIN,
                    osgb_id=osgb.id,
                    company_id=company.id,
                    is_active=True,
                ),
                Employee(
                    company_id=company.id,
                    full_name="Personel A",
                    job_title="Teknisyen",
                    department="Uretim",
                    is_active=True,
                ),
            ]
        )
        db.commit()

    return TestClient(app)


def _headers(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _ids() -> tuple[int, int]:
    import app.core.database as dbmod
    from app.models.entities import Employee

    with dbmod.SessionLocal() as db:
        emp = db.query(Employee).first()
        return emp.company_id, emp.id


def _payload(company_id: int, employee_id: int, **over) -> dict:
    base = {
        "company_id": company_id,
        "employee_id": employee_id,
        "record_type": "periodic_exam",
        "examination_date": "2026-03-10",
        "fitness_status": "fit",
        "summary": "Periyodik muayene bulgulari uygun",
        "informed_consent": True,
    }
    base.update(over)
    return base


def test_create_rejected_without_informed_consent(client):
    headers = _headers(client, "onam-hekim@test.com", "HekimPass123!")
    company_id, employee_id = _ids()

    r = client.post(
        "/api/v1/health-records",
        headers=headers,
        json=_payload(company_id, employee_id, informed_consent=False),
    )
    assert r.status_code == 400, r.text
    assert "onay" in r.json()["detail"].casefold()


def test_create_with_consent_stamps_time(client):
    headers = _headers(client, "onam-hekim@test.com", "HekimPass123!")
    company_id, employee_id = _ids()

    r = client.post(
        "/api/v1/health-records",
        headers=headers,
        json=_payload(company_id, employee_id),
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body["informed_consent"] is True
    assert body["informed_consent_at"]


def test_duplicate_exam_same_day_rejected(client):
    headers = _headers(client, "onam-hekim@test.com", "HekimPass123!")
    company_id, employee_id = _ids()

    first = client.post(
        "/api/v1/health-records", headers=headers, json=_payload(company_id, employee_id)
    )
    assert first.status_code in (200, 201), first.text

    again = client.post(
        "/api/v1/health-records", headers=headers, json=_payload(company_id, employee_id)
    )
    assert again.status_code == 400, again.text
    assert "zaten var" in again.json()["detail"].casefold()

    # Farklı tarih engellenmez
    other_day = client.post(
        "/api/v1/health-records",
        headers=headers,
        json=_payload(company_id, employee_id, examination_date="2026-04-11"),
    )
    assert other_day.status_code in (200, 201), other_day.text


def test_osgb_admin_cannot_reach_health_records(client):
    """OSGB merkez yöneticisi çalışanların tıbbi kaydını göremez/açamaz."""
    headers = _headers(client, "onam-osgb@test.com", "OsgbPass123!")
    company_id, employee_id = _ids()

    listed = client.get(f"/api/v1/health-records?company_id={company_id}", headers=headers)
    assert listed.status_code == 403, listed.text

    created = client.post(
        "/api/v1/health-records", headers=headers, json=_payload(company_id, employee_id)
    )
    assert created.status_code == 403, created.text


def test_restrictions_encrypted_at_rest_and_hidden_from_dsp(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "health_field_encryption_enabled", True)
    headers = _headers(client, "onam-hekim@test.com", "HekimPass123!")
    company_id, employee_id = _ids()
    limit_text = "Agir kaldirma ve gece vardiyasi yapmamali"

    created = client.post(
        "/api/v1/health-records",
        headers=headers,
        json=_payload(company_id, employee_id, restrictions=limit_text),
    )
    assert created.status_code in (200, 201), created.text
    record_id = created.json()["id"]
    assert created.json()["restrictions"] == limit_text

    import app.core.database as dbmod
    from app.models.entities import HealthRecord

    with dbmod.SessionLocal() as db:
        stored = db.get(HealthRecord, record_id).restrictions
    assert stored.startswith("enc:v1:")
    assert limit_text not in stored

    dsp = _headers(client, "onam-dsp@test.com", "DspPass12345!")
    rows = client.get(f"/api/v1/health-records?company_id={company_id}", headers=dsp)
    assert rows.status_code == 200, rows.text
    row = next(x for x in rows.json() if x["id"] == record_id)
    assert row["restrictions"] is None
