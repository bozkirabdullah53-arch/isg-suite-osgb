"""İşyeri yetkilisi modülleri ve tek-işyeri izolasyonu regresyon testleri."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def workplace_client(tmp_path, monkeypatch):
    db_file = tmp_path / "workplace-manager.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "workplace-test-secret-key-at-least-32-chars")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "workplace-test-secret-key-at-least-32-chars"
    settings.environment = "development"

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.core.security import get_password_hash
    from app.models.entities import (
        ArchiveKind,
        Company,
        EisaArchiveRecord,
        Employee,
        OsgbOrganization,
        User,
        UserRole,
        WorkplaceMembership,
    )

    password = "TestPass123!"
    with dbmod.SessionLocal() as db:
        osgb = OsgbOrganization(name="Yetkili Test OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        own = Company(
            name="Yetkilinin İşyeri",
            osgb_id=osgb.id,
            authorized_person="İşyeri Yetkilisi",
            is_active=True,
        )
        foreign = Company(name="Başka İşyeri", osgb_id=osgb.id, is_active=True)
        db.add_all([own, foreign])
        db.flush()
        manager = User(
            email="ik.yetkilisi@example.com",
            full_name="İK Yetkilisi",
            hashed_password=get_password_hash(password),
            role=UserRole.COMPANY_ADMIN,
            company_id=own.id,
            osgb_id=osgb.id,
            is_active=True,
        )
        osgb_admin = User(
            email="osgb.admin@example.com",
            full_name="OSGB Admin",
            hashed_password=get_password_hash(password),
            role=UserRole.COMPANY_ADMIN,
            company_id=None,
            osgb_id=osgb.id,
            is_active=True,
        )
        global_admin = User(
            email="global.admin@example.com",
            full_name="Global Admin",
            hashed_password=get_password_hash(password),
            role=UserRole.GLOBAL_ADMIN,
            company_id=None,
            osgb_id=None,
            is_active=True,
        )
        kiosk = User(
            email=f"isyeri.{own.id}@kiosk.isgsuite.tr",
            full_name="İşyeri QR",
            hashed_password=get_password_hash(password),
            role=UserRole.COMPANY_ADMIN,
            company_id=own.id,
            osgb_id=osgb.id,
            is_active=True,
        )
        foreign_user = User(
            email="baska.isyeri@example.com",
            full_name="Başka İşyeri Yetkilisi",
            hashed_password=get_password_hash(password),
            role=UserRole.COMPANY_ADMIN,
            company_id=foreign.id,
            osgb_id=osgb.id,
            is_active=True,
        )
        db.add_all([manager, osgb_admin, global_admin, kiosk, foreign_user])
        db.flush()
        # Eski/hatalı üyelik işyeri hesabının kapsamını genişletmemeli.
        db.add(
            WorkplaceMembership(
                user_id=manager.id,
                company_id=foreign.id,
                role="company_admin",
                is_active=True,
            )
        )
        own_employee = Employee(company_id=own.id, full_name="Mevcut Çalışan", is_active=True)
        foreign_employee = Employee(company_id=foreign.id, full_name="Yabancı Çalışan", is_active=True)
        db.add_all([own_employee, foreign_employee])
        own_archive = EisaArchiveRecord(
            kind=ArchiveKind.DELETED_FILE,
            osgb_id=osgb.id,
            company_id=own.id,
            original_name="kendi-belgesi.pdf",
            storage_path="test/kendi-belgesi.pdf",
            size_bytes=10,
            created_by_user_id=manager.id,
        )
        foreign_archive = EisaArchiveRecord(
            kind=ArchiveKind.DELETED_FILE,
            osgb_id=osgb.id,
            company_id=foreign.id,
            original_name="yabanci-belge.pdf",
            storage_path="test/yabanci-belge.pdf",
            size_bytes=20,
            created_by_user_id=foreign_user.id,
        )
        db.add_all([own_archive, foreign_archive])
        db.commit()
        seed = {
            "osgb_id": osgb.id,
            "own_company_id": own.id,
            "foreign_company_id": foreign.id,
            "own_employee_id": own_employee.id,
            "foreign_employee_id": foreign_employee.id,
            "foreign_user_id": foreign_user.id,
            "own_archive_id": own_archive.id,
            "foreign_archive_id": foreign_archive.id,
            "manager_email": manager.email,
            "osgb_admin_email": osgb_admin.email,
            "global_admin_email": global_admin.email,
            "kiosk_email": kiosk.email,
            "password": password,
        }

    from app.main import app

    return TestClient(app), seed


def _token(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_workplace_manager_account_includes_existing_qr_account_but_not_osgb_admin():
    from app.api.deps import is_workplace_manager_account
    from app.models.entities import UserRole

    manager = SimpleNamespace(
        role=UserRole.COMPANY_ADMIN,
        company_id=4,
        email="ik@example.com",
    )
    osgb_admin = SimpleNamespace(
        role=UserRole.COMPANY_ADMIN,
        company_id=None,
        email="admin@example.com",
    )
    kiosk = SimpleNamespace(
        role=UserRole.COMPANY_ADMIN,
        company_id=4,
        email="isyeri.4@kiosk.isgsuite.tr",
    )

    assert is_workplace_manager_account(manager) is True
    assert is_workplace_manager_account(osgb_admin) is False
    assert is_workplace_manager_account(kiosk) is True


@pytest.mark.parametrize("account_key", ["manager_email", "kiosk_email"])
def test_workplace_manager_can_write_target_modules_only_in_own_company(workplace_client, account_key):
    client, seed = workplace_client
    own = seed["own_company_id"]
    foreign = seed["foreign_company_id"]
    token = _token(client, seed[account_key], seed["password"])
    headers = _headers(token)
    global_token = _token(client, seed["global_admin_email"], seed["password"])
    global_headers = _headers(global_token)

    # Yabancı tenantta gerçek kayıtlar oluştur; yalnız create payload'ı değil,
    # doğrudan kayıt kimliğiyle okuma/güncelleme denemeleri de sınansın.
    foreign_periodic = client.post(
        "/api/v1/periodic-controls",
        headers=global_headers,
        json={"company_id": foreign, "category": "elektrik", "equipment_name": "Yabancı Pano"},
    )
    assert foreign_periodic.status_code == 200, foreign_periodic.text
    foreign_measurement = client.post(
        "/api/v1/workplace-measurements",
        headers=global_headers,
        json={
            "company_id": foreign,
            "measurement_type": "gurultu",
            "measured_at": date.today().isoformat(),
        },
    )
    assert foreign_measurement.status_code == 200, foreign_measurement.text
    foreign_sds = client.post(
        "/api/v1/sds",
        headers=global_headers,
        json={"company_id": foreign, "product_name": "Yabancı Ürün"},
    )
    assert foreign_sds.status_code == 200, foreign_sds.text
    foreign_ppe = client.post(
        "/api/v1/ppe/assignments",
        headers=global_headers,
        json={
            "company_id": foreign,
            "employee_id": seed["foreign_employee_id"],
            "delivery_date": date.today().isoformat(),
            "category": "Baş Koruyucular",
            "item_type": "Baret",
        },
    )
    assert foreign_ppe.status_code == 200, foreign_ppe.text
    foreign_incident_payload = {
        "company_id": foreign,
        "event_type": "ramak_kala",
        "short_summary": "Yabancı işyerinde malzeme düşmesi olayı yaşandı",
        "event_date": date.today().isoformat(),
        "location": "Yabancı üretim alanı",
        "detail": "Yabancı işyerindeki raftan malzeme aşağı doğru kayarak düştü.",
        "classification": "Düşen cisim",
    }
    foreign_incident = client.post(
        "/api/v1/incidents", headers=global_headers, json=foreign_incident_payload
    )
    assert foreign_incident.status_code == 200, foreign_incident.text

    assert client.patch(
        f"/api/v1/periodic-controls/{foreign_periodic.json()['id']}",
        headers=headers,
        json={"notes": "Yetkisiz değişiklik"},
    ).status_code == 403
    assert client.patch(
        f"/api/v1/workplace-measurements/{foreign_measurement.json()['id']}",
        headers=headers,
        json={"notes": "Yetkisiz değişiklik"},
    ).status_code == 403
    assert client.patch(
        f"/api/v1/sds/{foreign_sds.json()['id']}",
        headers=headers,
        json={"notes": "Yetkisiz değişiklik"},
    ).status_code == 403
    assert client.get(
        f"/api/v1/sds/{foreign_sds.json()['id']}/ghs-checklist", headers=headers
    ).status_code == 403
    assert client.get(
        f"/api/v1/ppe/assignments/{foreign_ppe.json()['id']}", headers=headers
    ).status_code == 403
    assert client.get(
        f"/api/v1/incidents/{foreign_incident.json()['id']}", headers=headers
    ).status_code == 403

    companies = client.get("/api/v1/companies", headers=headers)
    assert companies.status_code == 200, companies.text
    assert [row["id"] for row in companies.json()] == [own]

    employees = client.get("/api/v1/employees", headers=headers)
    assert employees.status_code == 200, employees.text
    assert {row["company_id"] for row in employees.json()} == {own}
    assert client.get(
        "/api/v1/employees", headers=headers, params={"company_id": foreign}
    ).status_code == 403

    created_employee = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "company_id": own,
            "full_name": "Yeni İşe Giren",
            "job_title": "Üretim Personeli",
            "start_date": date.today().isoformat(),
        },
    )
    assert created_employee.status_code == 200, created_employee.text
    assert created_employee.json()["company_id"] == own
    updated_employee = client.put(
        f"/api/v1/employees/{created_employee.json()['id']}",
        headers=headers,
        json={
            "full_name": "Düzeltilmiş Çalışan Adı",
            "job_title": "Güvenli Üretim Personeli",
            "department": "Üretim",
            "special_status": "—",
        },
    )
    assert updated_employee.status_code == 200, updated_employee.text
    assert updated_employee.json()["full_name"] == "Düzeltilmiş Çalışan Adı"
    assert updated_employee.json()["job_title"] == "Güvenli Üretim Personeli"
    assert updated_employee.json()["department"] == "Üretim"
    assert client.post(
        "/api/v1/employees",
        headers=headers,
        json={"company_id": foreign, "full_name": "Yabancı Firmaya Ekleme"},
    ).status_code == 403
    assert client.put(
        f"/api/v1/employees/{seed['foreign_employee_id']}",
        headers=headers,
        json={"job_title": "Yetkisiz Değişiklik"},
    ).status_code == 403
    assert client.delete(
        f"/api/v1/employees/{seed['foreign_employee_id']}", headers=headers
    ).status_code == 403

    periodic = client.post(
        "/api/v1/periodic-controls",
        headers=headers,
        json={"company_id": own, "category": "elektrik", "equipment_name": "Ana Elektrik Panosu"},
    )
    assert periodic.status_code == 200, periodic.text
    assert client.post(
        "/api/v1/periodic-controls",
        headers=headers,
        json={"company_id": foreign, "category": "elektrik", "equipment_name": "Yabancı Pano"},
    ).status_code == 403

    measurement = client.post(
        "/api/v1/workplace-measurements",
        headers=headers,
        json={
            "company_id": own,
            "measurement_type": "gurultu",
            "location": "Üretim alanı",
            "measured_at": date.today().isoformat(),
        },
    )
    assert measurement.status_code == 200, measurement.text
    assert client.post(
        "/api/v1/workplace-measurements",
        headers=headers,
        json={
            "company_id": foreign,
            "measurement_type": "gurultu",
            "measured_at": date.today().isoformat(),
        },
    ).status_code == 403

    sds = client.post(
        "/api/v1/sds",
        headers=headers,
        json={"company_id": own, "product_name": "Temizlik Kimyasalı"},
    )
    assert sds.status_code == 200, sds.text
    assert client.post(
        "/api/v1/sds",
        headers=headers,
        json={"company_id": foreign, "product_name": "Yabancı Kimyasal"},
    ).status_code == 403

    ppe = client.post(
        "/api/v1/ppe/assignments",
        headers=headers,
        json={
            "company_id": own,
            "employee_id": created_employee.json()["id"],
            "delivery_date": date.today().isoformat(),
            "category": "Baş Koruyucular",
            "item_type": "Baret",
        },
    )
    assert ppe.status_code == 200, ppe.text
    assert client.post(
        "/api/v1/ppe/assignments",
        headers=headers,
        json={
            "company_id": foreign,
            "employee_id": seed["own_employee_id"],
            "delivery_date": date.today().isoformat(),
            "category": "Baş Koruyucular",
            "item_type": "Baret",
        },
    ).status_code == 403

    incident_payload = {
        "event_type": "ramak_kala",
        "short_summary": "Malzeme düşmesine ramak kala olayı yaşandı",
        "event_date": date.today().isoformat(),
        "location": "Üretim alanı",
        "detail": "Raf üzerindeki malzeme sabitlenmediği için aşağı doğru kaydı.",
        "classification": "Düşen cisim",
    }
    incident = client.post(
        "/api/v1/incidents",
        headers=headers,
        json={**incident_payload, "company_id": own},
    )
    assert incident.status_code == 200, incident.text
    assert client.post(
        "/api/v1/incidents",
        headers=headers,
        json={**incident_payload, "company_id": foreign},
    ).status_code == 403

    oversight = client.get(f"/api/v1/companies/{own}/employer-oversight", headers=headers)
    assert oversight.status_code == 200, oversight.text
    assert client.get(f"/api/v1/companies/{own}/overview", headers=headers).status_code == 403
    assert client.get(
        f"/api/v1/companies/{foreign}/employer-oversight", headers=headers
    ).status_code == 403

    for path in ("/api/v1/periodic-controls", "/api/v1/workplace-measurements", "/api/v1/sds"):
        listed = client.get(path, headers=headers)
        assert listed.status_code == 200, listed.text
        assert {row["company_id"] for row in listed.json()} <= {own}

    # Salt-okunur modüller: GET çalışır, mutasyon backend'de reddedilir.
    documents = client.get("/api/v1/documents", headers=headers)
    assert documents.status_code == 200, documents.text
    assert client.post(
        "/api/v1/documents",
        headers=headers,
        json={"company_id": own, "category": "general", "title": "Salt Okunur Belge"},
    ).status_code == 403

    health_cards = client.get("/api/v1/workplace/health-cards", headers=headers)
    assert health_cards.status_code == 200, health_cards.text
    assert health_cards.json()["company_id"] == own
    assert {row["employee_id"] for row in health_cards.json()["personnel"]} <= {
        seed["own_employee_id"], created_employee.json()["id"]
    }


def test_workplace_manager_direct_api_scope_stays_inside_own_workplace(workplace_client):
    client, seed = workplace_client
    own = seed["own_company_id"]
    foreign = seed["foreign_company_id"]
    headers = _headers(_token(client, seed["manager_email"], seed["password"]))

    # Aynı osgb_id, işyeri hesabını OSGB yöneticisine dönüştürmemeli.
    users = client.get("/api/v1/users", headers=headers)
    assert users.status_code == 200, users.text
    assert users.json()
    assert {row["company_id"] for row in users.json()} == {own}
    assert client.patch(
        f"/api/v1/users/{seed['foreign_user_id']}/suspend", headers=headers
    ).status_code == 403

    membership_me = client.get("/api/v1/memberships/me", headers=headers)
    assert membership_me.status_code == 200, membership_me.text
    assert membership_me.json()["company_ids"] == [own]
    workplace_memberships = client.get("/api/v1/memberships/workplace", headers=headers)
    assert workplace_memberships.status_code == 403, workplace_memberships.text
    assert client.get("/api/v1/memberships/organization", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/memberships/workplace",
        headers=headers,
        json={
            "user_id": seed["foreign_user_id"],
            "company_id": foreign,
            "role": "company_admin",
        },
    ).status_code == 403

    archives = client.get("/api/v1/archives", headers=headers)
    assert archives.status_code == 200, archives.text
    assert [row["id"] for row in archives.json()] == [seed["own_archive_id"]]
    assert client.get(
        f"/api/v1/archives/{seed['foreign_archive_id']}/download", headers=headers
    ).status_code == 403
    assert client.post(
        "/api/v1/archives/backup",
        headers=headers,
        json={"company_id": foreign},
    ).status_code == 403

    # İşyeri kartı okunabilir; OSGB'nin işyeri oluşturma/değiştirme ekranı açılamaz.
    assert client.get(f"/api/v1/companies/{own}", headers=headers).status_code == 200
    assert client.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Yetkisiz Yeni İşyeri", "sgk_registry_no": "12345"},
    ).status_code == 403
    assert client.put(
        f"/api/v1/companies/{own}",
        headers=headers,
        json={"authorized_person": "Yetkisiz Değişiklik"},
    ).status_code == 403


@pytest.mark.parametrize("account_key", ["manager_email", "kiosk_email"])
def test_company_bound_admin_cannot_open_osgb_internal_apis(workplace_client, account_key):
    client, seed = workplace_client
    headers = _headers(_token(client, seed[account_key], seed["password"]))

    for path in (
        "/api/v1/operations/dashboard",
        "/api/v1/osgb/professionals",
        f"/api/v1/osgb-personnel-profiles/readiness?osgb_id={seed['osgb_id']}",
        "/api/v1/subscriptions/osgb/current",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 403, (path, response.text)


def test_osgb_admin_keeps_existing_osgb_internal_access(workplace_client):
    client, seed = workplace_client
    headers = _headers(_token(client, seed["osgb_admin_email"], seed["password"]))

    dashboard = client.get("/api/v1/operations/dashboard", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    professionals = client.get("/api/v1/osgb/professionals", headers=headers)
    assert professionals.status_code == 200, professionals.text
    subscription = client.get("/api/v1/subscriptions/osgb/current", headers=headers)
    assert subscription.status_code == 200, subscription.text


def test_rls_admin_flag_excludes_workplace_manager_and_kiosk():
    from app.core.rls import _has_osgb_admin_rls_privilege
    from app.models.entities import UserRole

    osgb_admin = SimpleNamespace(
        role=UserRole.COMPANY_ADMIN,
        company_id=None,
    )
    workplace_manager = SimpleNamespace(
        role=UserRole.COMPANY_ADMIN,
        company_id=7,
    )
    global_admin = SimpleNamespace(
        role=UserRole.GLOBAL_ADMIN,
        company_id=None,
    )

    assert _has_osgb_admin_rls_privilege(global_admin) is True
    assert _has_osgb_admin_rls_privilege(osgb_admin) is True
    assert _has_osgb_admin_rls_privilege(workplace_manager) is False


def test_osgb_admin_does_not_gain_workplace_register_access(workplace_client):
    client, seed = workplace_client
    own = seed["own_company_id"]
    token = _token(client, seed["osgb_admin_email"], seed["password"])
    headers = _headers(token)

    assert client.get("/api/v1/sds", headers=headers).status_code == 403
    assert client.get("/api/v1/periodic-controls", headers=headers).status_code == 403
    assert client.get("/api/v1/workplace-measurements", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/sds",
        headers=headers,
        json={"company_id": own, "product_name": "Yetkisiz Ürün"},
    ).status_code == 403
