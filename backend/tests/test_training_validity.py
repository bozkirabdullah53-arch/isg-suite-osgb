"""Çalışan bazlı temel İSG eğitimi geçerliliği.

Yönetmelik md.6: işe başlamadan önce eğitim; md.11: az tehlikeli 3, tehlikeli 2,
çok tehlikeli 1 yılda bir yenileme. Kayıt bazlı yenileme tarihi çalışan bazına
indirgenir; hiç eğitim almamış personel de listelenir.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.services.training_validity import (
    DUE_SOON_DAYS,
    evaluate_employee,
    renewal_years,
    summarize,
)


def test_renewal_years_by_hazard_class():
    assert renewal_years("Az Tehlikeli") == 3
    assert renewal_years("Tehlikeli") == 2
    assert renewal_years("Çok Tehlikeli") == 1
    assert renewal_years(None) is None


def test_employee_without_training_is_never_status():
    body = evaluate_employee(
        hire_date=date(2026, 1, 10), last_training_end=None, today=date(2026, 7, 28)
    )
    assert body["status"] == "never"
    assert body["next_due"] is None
    assert "işe başlamadan önce" in body["message"]
    assert "10.01.2026" in body["message"]


def test_expired_due_soon_and_ok():
    today = date(2026, 7, 28)

    expired = evaluate_employee(
        last_training_end=date(2023, 1, 1), next_due=date(2025, 1, 1), today=today
    )
    assert expired["status"] == "expired"
    assert expired["days_left"] < 0

    soon = evaluate_employee(
        last_training_end=date(2025, 8, 1),
        next_due=today + timedelta(days=DUE_SOON_DAYS - 1),
        today=today,
    )
    assert soon["status"] == "due_soon"

    ok = evaluate_employee(
        last_training_end=date(2026, 1, 1), next_due=date(2028, 1, 1), today=today
    )
    assert ok["status"] == "ok"


def test_training_without_due_date_counts_as_expired():
    body = evaluate_employee(last_training_end=date(2020, 1, 1), next_due=None)
    assert body["status"] == "expired"
    assert "hesaplanamadı" in body["message"]


def test_summary_counts_and_compliance_rate():
    rows = [
        {"status": "ok"},
        {"status": "ok"},
        {"status": "expired"},
        {"status": "never"},
    ]
    body = summarize(rows)
    assert body["total_employees"] == 4
    assert body["ok"] == 2
    assert body["action_needed"] == 2
    assert body["compliance_rate"] == 50.0


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "training_validity.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.core.database as dbmod
    import app.models.entities as ent
    # NACE snapshot mapper registers its table before the isolated test schema
    # is created; production startup imports this mapper through the API.
    import app.models.training_nace  # noqa: F401
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    # Şema bu izole testte create_all ile kuruldu; uygulama başlangıcının
    # development onarım kancası ikinci kez aynı indeksleri üretmesin.
    settings.environment = "production"
    settings.upload_dir = str(tmp_path / "uploads")

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed(
    client: TestClient,
    with_assignment: bool = True,
    role: UserRole | None = None,
) -> dict:
    """3 personel: biri geçerli, biri süresi dolmuş, biri hiç eğitimsiz."""
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        Employee,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        TrainingParticipant,
        TrainingSession,
        TrainingStatus,
        User,
        UserRole,
        WorkplaceAssignment,
    )

    today = date.today()
    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Egitim OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(name="Egitim Firma", hazard_class="Tehlikeli", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        user = User(
            email="egitim-uzman@test.com",
            full_name="Egitim Uzman",
            hashed_password=get_password_hash("TestPass123!"),
            role=role or UserRole.SAFETY_SPECIALIST,
            osgb_id=osgb.id,
            company_id=company.id,
            is_active=True,
        )
        db.add(user)
        db.flush()
        professional = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Egitim Uzman",
            email="egitim-uzman@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="B",
            certificate_number="TEST-UZM-1",
            is_active=True,
        )
        db.add(professional)

        gecerli = Employee(company_id=company.id, full_name="Gecerli Kisi", department="Uretim", is_active=True)
        dolmus = Employee(company_id=company.id, full_name="Dolmus Kisi", department="Depo", is_active=True)
        egitimsiz = Employee(
            company_id=company.id,
            full_name="Egitimsiz Kisi",
            department="Uretim",
            start_date=today - timedelta(days=45),
            is_active=True,
        )
        db.add_all([gecerli, dolmus, egitimsiz])
        db.flush()
        if with_assignment:
            db.add(
                WorkplaceAssignment(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    professional_id=professional.id,
                    professional_type=professional.professional_type,
                    start_date=today - timedelta(days=30),
                    status=AssignmentStatus.ACTIVE,
                )
            )

        yeni = TrainingSession(
            company_id=company.id,
            title="Temel İş Sağlığı ve Güvenliği Eğitimi",
            start_date=today - timedelta(days=30),
            end_date=today - timedelta(days=30),
            next_training_date=today + timedelta(days=700),
            hazard_class="Tehlikeli",
            duration_hours=12,
            renewal_years=2,
            instructor_name="Egitim Uzman",
            status=TrainingStatus.COMPLETED,
            created_by_id=user.id,
        )
        eski = TrainingSession(
            company_id=company.id,
            title="Temel İş Sağlığı ve Güvenliği Eğitimi",
            start_date=today - timedelta(days=1200),
            end_date=today - timedelta(days=1200),
            next_training_date=today - timedelta(days=470),
            hazard_class="Tehlikeli",
            duration_hours=12,
            renewal_years=2,
            instructor_name="Egitim Uzman",
            status=TrainingStatus.COMPLETED,
            created_by_id=user.id,
        )
        db.add_all([yeni, eski])
        db.flush()
        db.add_all(
            [
                TrainingParticipant(training_id=yeni.id, employee_id=gecerli.id),
                TrainingParticipant(training_id=eski.id, employee_id=dolmus.id),
            ]
        )
        db.commit()
        return {
            "company_id": company.id,
            "gecerli": gecerli.id,
            "dolmus": dolmus.id,
            "egitimsiz": egitimsiz.id,
        }


def _headers(client: TestClient) -> dict:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "egitim-uzman@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_employee_status_endpoint_classifies_everyone(client):
    seed = _seed(client)
    headers = _headers(client)

    r = client.get(f"/api/v1/trainings/employee-status?company_id={seed['company_id']}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["summary"]["total_employees"] == 3
    assert body["summary"]["ok"] == 1
    assert body["summary"]["expired"] == 1
    assert body["summary"]["never"] == 1
    assert body["summary"]["action_needed"] == 2

    by_id = {row["employee_id"]: row for row in body["rows"]}
    assert by_id[seed["gecerli"]]["status"] == "ok"
    assert by_id[seed["dolmus"]]["status"] == "expired"
    assert by_id[seed["egitimsiz"]]["status"] == "never"
    assert by_id[seed["egitimsiz"]]["department"] == "Uretim"

    # Hiç eğitimsiz en üstte, sonra gecikmiş
    assert body["rows"][0]["employee_id"] == seed["egitimsiz"]
    assert body["rows"][1]["employee_id"] == seed["dolmus"]


def test_employee_status_filter(client):
    seed = _seed(client)
    headers = _headers(client)
    r = client.get(
        f"/api/v1/trainings/employee-status?company_id={seed['company_id']}&status=expired",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [row["employee_id"] for row in body["rows"]] == [seed["dolmus"]]
    # Özet filtreden etkilenmez
    assert body["summary"]["total_employees"] == 3


def test_special_training_does_not_reset_basic_clock(client):
    """Yüksekte çalışma eğitimi temel eğitim yerine geçmez."""
    from app.core.database import SessionLocal
    from app.models.entities import TrainingParticipant, TrainingSession, TrainingStatus, User
    from sqlalchemy import select as sa_select

    seed = _seed(client)
    headers = _headers(client)
    today = date.today()

    with SessionLocal() as db:
        author = db.scalar(sa_select(User).where(User.email == "egitim-uzman@test.com"))
        ozel = TrainingSession(
            company_id=seed["company_id"],
            title="Yüksekte Çalışma Eğitimi",
            training_type="Yüksekte Çalışma",
            start_date=today - timedelta(days=5),
            end_date=today - timedelta(days=5),
            next_training_date=today + timedelta(days=360),
            hazard_class="Tehlikeli",
            duration_hours=8,
            renewal_years=1,
            instructor_name="Egitim Uzman",
            status=TrainingStatus.COMPLETED,
            created_by_id=author.id,
        )
        db.add(ozel)
        db.flush()
        db.add(TrainingParticipant(training_id=ozel.id, employee_id=seed["egitimsiz"]))
        db.commit()

    body = client.get(
        f"/api/v1/trainings/employee-status?company_id={seed['company_id']}", headers=headers
    ).json()
    by_id = {row["employee_id"]: row for row in body["rows"]}
    assert by_id[seed["egitimsiz"]]["status"] == "never"


def test_cancelled_training_is_ignored(client):
    from app.core.database import SessionLocal
    from app.models.entities import TrainingSession, TrainingStatus
    from sqlalchemy import select as sa_select

    seed = _seed(client)
    headers = _headers(client)

    with SessionLocal() as db:
        row = db.scalar(
            sa_select(TrainingSession)
            .where(TrainingSession.company_id == seed["company_id"])
            .order_by(TrainingSession.start_date.desc())
        )
        row.status = TrainingStatus.CANCELLED
        db.commit()

    body = client.get(
        f"/api/v1/trainings/employee-status?company_id={seed['company_id']}", headers=headers
    ).json()
    by_id = {row["employee_id"]: row for row in body["rows"]}
    assert by_id[seed["gecerli"]]["status"] == "never"


def test_assigned_team_fills_instructor_and_physician(client):
    """Eğitici/hekim adı görevlendirmeden gelmeli; elle yazmaya gerek kalmamalı."""
    from app.core.database import SessionLocal
    from app.models.entities import (
        AssignmentStatus,
        Company,
        IsgProfessional,
        ProfessionalType,
        WorkplaceAssignment,
    )
    from sqlalchemy import select as sa_select

    seed = _seed(client)
    headers = _headers(client)
    cid = seed["company_id"]

    with SessionLocal() as db:
        company = db.get(Company, cid)
        company.authorized_person = "Isveren Vekili"
        specialist = IsgProfessional(
            osgb_id=company.osgb_id,
            full_name="Uzman Kisi",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="B",
            certificate_number="UZM-1",
            is_active=True,
        )
        physician = IsgProfessional(
            osgb_id=company.osgb_id,
            full_name="Hekim Kisi",
            professional_type=ProfessionalType.WORKPLACE_PHYSICIAN,
            certificate_number="HKM-1",
            is_active=True,
        )
        db.add_all([specialist, physician])
        db.flush()
        for pro in (specialist, physician):
            db.add(
                WorkplaceAssignment(
                    osgb_id=company.osgb_id,
                    company_id=cid,
                    professional_id=pro.id,
                    professional_type=pro.professional_type,
                    start_date=date.today(),
                    status=AssignmentStatus.ACTIVE,
                )
            )
        db.commit()

    body = client.get(f"/api/v1/trainings/assigned-team?company_id={cid}", headers=headers).json()
    assert body["defaults"]["instructor_name"] == "Uzman Kisi"
    assert body["defaults"]["instructor_qualification"] == "B Sınıfı İş Güvenliği Uzmanı"
    assert body["defaults"]["workplace_physician"] == "Hekim Kisi"
    assert body["defaults"]["employer_representative"] == "Isveren Vekili"
    names = [o["value"] for o in body["instructor_options"]]
    assert names == ["Uzman Kisi", "Hekim Kisi"]


def test_assigned_team_empty_when_no_assignment(client):
    from app.models.entities import UserRole

    seed = _seed(client, with_assignment=False, role=UserRole.COMPANY_ADMIN)
    headers = _headers(client)
    body = client.get(
        f"/api/v1/trainings/assigned-team?company_id={seed['company_id']}", headers=headers
    ).json()
    assert body["defaults"]["instructor_name"] is None
    assert body["instructor_options"] == []


def test_employee_status_requires_company_access(client):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import Company, IsgProfessional, OsgbOrganization, ProfessionalType, User, UserRole

    seed = _seed(client)
    with SessionLocal() as db:
        other_osgb = OsgbOrganization(name="Diger OSGB", is_active=True)
        db.add(other_osgb)
        db.flush()
        other_company = Company(name="Diger Firma", hazard_class="Tehlikeli", osgb_id=other_osgb.id, is_active=True)
        db.add(other_company)
        db.flush()
        db.add(
            IsgProfessional(
                osgb_id=other_osgb.id,
                full_name="Diger Uzman",
                email="diger-uzman@test.com",
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                certificate_class="B",
                certificate_number="TEST-UZM-2",
                is_active=True,
            )
        )
        db.add(
            User(
                email="diger-uzman@test.com",
                full_name="Diger Uzman",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.SAFETY_SPECIALIST,
                osgb_id=other_osgb.id,
                company_id=other_company.id,
                is_active=True,
            )
        )
        db.commit()

    r = client.post(
        "/api/v1/auth/login", json={"email": "diger-uzman@test.com", "password": "TestPass123!"}
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    blocked = client.get(
        f"/api/v1/trainings/employee-status?company_id={seed['company_id']}", headers=headers
    )
    assert blocked.status_code == 403
