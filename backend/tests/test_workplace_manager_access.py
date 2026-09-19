"""İşyeri yetkilisi modülleri ve tek-işyeri izolasyonu regresyon testleri."""
from __future__ import annotations

from datetime import date, datetime
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

    from sqlalchemy import create_engine, inspect
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
    with engine.begin() as connection:
        inspector = inspect(connection)
        member_columns = {
            "employee_id": "INTEGER",
            "user_id": "INTEGER",
            "branch_id": "INTEGER",
            "identity_key": "VARCHAR(220)",
            "source_type": "VARCHAR(40)",
            "source_ref": "VARCHAR(120)",
            "job_title_snapshot": "VARCHAR(160)",
            "professional_role_snapshot": "VARCHAR(160)",
            "email_snapshot": "VARCHAR(255)",
            "is_mandatory": "BOOLEAN NOT NULL DEFAULT 0",
            "removed_at": "DATETIME",
            "removed_by_id": "INTEGER",
            "removal_reason_code": "VARCHAR(60)",
            "removal_reason_text": "VARCHAR(1000)",
            "removal_document_version": "INTEGER",
        }
        meeting_columns = {
            "title": "VARCHAR(220)",
            "meeting_no": "VARCHAR(60)",
            "document_no": "VARCHAR(80)",
            "revision_no": "VARCHAR(30) NOT NULL DEFAULT '00'",
            "status": "VARCHAR(40) NOT NULL DEFAULT 'draft'",
            "signature_status": "VARCHAR(40) NOT NULL DEFAULT 'not_signed'",
            "start_time": "VARCHAR(10)",
            "end_time": "VARCHAR(10)",
            "location": "VARCHAR(220)",
            "meeting_type": "VARCHAR(60)",
            "member_snapshot_json": "TEXT",
            "agenda_json": "TEXT",
            "decisions_json": "TEXT",
            "approval_reference": "VARCHAR(160)",
            "pdf_sha256": "VARCHAR(64)",
            "pdf_generated_at": "DATETIME",
            "approval_workflow_id": "INTEGER",
            "approval_status": "VARCHAR(50) NOT NULL DEFAULT 'draft'",
            "approval_current_step": "INTEGER",
            "document_version": "INTEGER NOT NULL DEFAULT 1",
            "approval_submitted_at": "DATETIME",
            "approval_completed_at": "DATETIME",
            "approval_invalidated_at": "DATETIME",
            "updated_at": "DATETIME",
        }
        for table, columns in (
            ("ohs_committee_members", member_columns),
            ("ohs_committee_meetings", meeting_columns),
        ):
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    connection.exec_driver_sql(
                        f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}'
                    )
        connection.exec_driver_sql(
            """
            CREATE TABLE ohs_committee_signature_steps (
                id INTEGER PRIMARY KEY,
                meeting_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                document_version INTEGER NOT NULL,
                step_order INTEGER NOT NULL,
                signer_user_id INTEGER NOT NULL,
                role_label VARCHAR(120) NOT NULL,
                status VARCHAR(40) NOT NULL DEFAULT 'pending',
                esign_request_id INTEGER,
                esign_artifact_id INTEGER,
                signed_at DATETIME,
                invalidated_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (meeting_id, document_version, step_order)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_committee_signature_company_status "
            "ON ohs_committee_signature_steps(company_id, status)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_committee_signature_signer_status "
            "ON ohs_committee_signature_steps(signer_user_id, status)"
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE ohs_committee_meeting_versions (
                id INTEGER PRIMARY KEY,
                meeting_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                document_version INTEGER NOT NULL,
                meeting_snapshot_json TEXT NOT NULL,
                member_snapshot_json TEXT,
                approval_workflow_id INTEGER,
                final_signature_artifact_id INTEGER,
                pdf_sha256 VARCHAR(64),
                archive_reason VARCHAR(120) NOT NULL DEFAULT 'material_change',
                created_by_id INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (meeting_id, document_version)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_committee_meeting_versions_company "
            "ON ohs_committee_meeting_versions(company_id, meeting_id)"
        )

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
            "manager_id": manager.id,
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


def test_workplace_summary_counts_all_rows_and_both_dof_sources(workplace_client):
    from app.core.database import SessionLocal
    from app.models.entities import (
        Hazard, HazardCategory, IncidentDof, IncidentEvent, PpeAssignment,
        RiskAssessment, RiskDof,
    )

    client, seed = workplace_client
    with SessionLocal() as db:
        ppe_fields = dict(
            company_id=seed['own_company_id'], employee_id=seed['own_employee_id'],
            created_by_id=seed['manager_id'], delivery_date=date.today(),
            category='Baş Koruyucular', item_type='Baret',
        )
        db.add_all([PpeAssignment(**ppe_fields) for _ in range(501)])
        db.add(PpeAssignment(**ppe_fields, deleted_at=datetime.utcnow()))
        db.add(PpeAssignment(**{
            **ppe_fields, 'company_id': seed['foreign_company_id'],
            'employee_id': seed['foreign_employee_id'],
        }))
        category = HazardCategory(name='Özet testi')
        db.add(category)
        db.flush()
        hazard = Hazard(category_id=category.id, code='SUMMARY', name='Kayma')
        db.add(hazard)
        db.flush()
        for scope, dof_count in [('own', 2), ('foreign', 3)]:
            risk = RiskAssessment(
                risk_code=f'R-{scope}', company_id=seed[f'{scope}_company_id'],
                hazard_id=hazard.id, activity='Üretim', risk_definition='Kayma tehlikesi',
                probability=2, severity=2, risk_score=4, risk_level='Düşük',
                created_by_id=seed['manager_id'],
            )
            incident = IncidentEvent(
                form_no=f'I-{scope}', company_id=seed[f'{scope}_company_id'],
                event_type='ramak_kala', event_date=date.today(),
                short_summary='Kayma olayı', created_by_id=seed['manager_id'],
            )
            db.add_all([risk, incident])
            db.flush()
            db.add_all([RiskDof(
                risk_id=risk.id, dof_code=f'D-{scope}-{number}', description='Zemini düzeltin',
                created_by_id=seed['manager_id'],
            ) for number in range(dof_count)])
            db.add(IncidentDof(
                incident_id=incident.id, dof_no=f'ID-{scope}', finding='Kaygan zemin',
                created_by_id=seed['manager_id'],
            ))
        db.commit()

    for account in ['manager_email', 'kiosk_email']:
        headers = _headers(_token(client, seed[account], seed['password']))
        response = client.get('/api/v1/workplace-portal/summary', headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()['counts'] == {
            'employees': 1, 'ppe': 501, 'sds': 0, 'periodic': 0, 'measurements': 0,
            'nearMiss': 1, 'accidents': 0, 'capa': 3,
        }
    headers = _headers(_token(client, seed['osgb_admin_email'], seed['password']))
    assert client.get('/api/v1/workplace-portal/summary', headers=headers).status_code == 403


def test_workplace_manager_can_manage_own_committee_without_eyas_assignment(monkeypatch):
    from app.models.entities import UserRole
    from app.services import committee_workflow

    manager = SimpleNamespace(
        role=UserRole.COMPANY_ADMIN,
        company_id=42,
        email="ik@example.com",
        id=9,
    )
    foreign_manager = SimpleNamespace(
        role=UserRole.COMPANY_ADMIN,
        company_id=99,
        email="baska@example.com",
        id=10,
    )
    osgb_admin = SimpleNamespace(
        role=UserRole.COMPANY_ADMIN,
        company_id=None,
        email="admin@example.com",
        id=11,
    )
    monkeypatch.setattr(committee_workflow, "assigned_participants", lambda *_args, **_kwargs: [])

    assert committee_workflow.can_manage_company(SimpleNamespace(), manager, 42) is True
    assert committee_workflow.can_manage_company(SimpleNamespace(), foreign_manager, 42) is False
    assert committee_workflow.can_manage_company(SimpleNamespace(), osgb_admin, 42) is False


def test_workplace_manager_account_excludes_osgb_admin_and_qr_kiosk():
    from app.api.deps import is_workplace_manager_account
    from app.core.rls import _has_workplace_health_read_privilege
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
    assert is_workplace_manager_account(kiosk) is False
    assert _has_workplace_health_read_privilege(manager) is True
    assert _has_workplace_health_read_privilege(osgb_admin) is False
    assert _has_workplace_health_read_privilege(kiosk) is False


def test_workplace_health_view_is_own_company_only_and_excludes_kiosk(workplace_client):
    from app.core.database import SessionLocal
    from app.models.entities import (
        HealthFitnessStatus,
        HealthRecord,
        HealthRecordType,
    )

    client, seed = workplace_client
    with SessionLocal() as db:
        db.add_all([
            HealthRecord(
                company_id=seed["own_company_id"],
                employee_id=seed["own_employee_id"],
                record_type=HealthRecordType.PERIODIC_EXAM,
                examination_date=date(2026, 7, 1),
                fitness_status=HealthFitnessStatus.CONDITIONAL,
                physician_name="Dr. Kendi",
                restrictions="Gece vardiyası yok",
                created_by_id=seed["manager_id"],
            ),
            HealthRecord(
                company_id=seed["foreign_company_id"],
                employee_id=seed["foreign_employee_id"],
                record_type=HealthRecordType.PERIODIC_EXAM,
                examination_date=date(2026, 7, 2),
                fitness_status=HealthFitnessStatus.FIT,
                physician_name="Dr. Yabancı",
                summary="YABANCI_KLINIK_BILGI",
                created_by_id=seed["foreign_user_id"],
            ),
        ])
        db.commit()

    manager_headers = _headers(
        _token(client, seed["manager_email"], seed["password"])
    )
    listed = client.get("/api/v1/health-records", headers=manager_headers)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    assert listed.json()[0]["company_id"] == seed["own_company_id"]
    assert listed.json()[0]["employee_name"] == "Mevcut Çalışan"
    assert listed.json()[0]["restrictions"] == "Gece vardiyası yok"
    assert "YABANCI_KLINIK_BILGI" not in listed.text

    foreign = client.get(
        f"/api/v1/health-records?company_id={seed['foreign_company_id']}",
        headers=manager_headers,
    )
    assert foreign.status_code == 403, foreign.text

    kiosk_headers = _headers(_token(client, seed["kiosk_email"], seed["password"]))
    assert client.get("/api/v1/health-records", headers=kiosk_headers).status_code == 403

    central_headers = _headers(
        _token(client, seed["osgb_admin_email"], seed["password"])
    )
    assert client.get("/api/v1/health-records", headers=central_headers).status_code == 403


def test_employee_purge_explains_archived_health_link_not_visible_in_active_list(workplace_client):
    """Soft-deleted health history blocks purge without being shown as active."""
    from app.core.database import SessionLocal
    from app.models.entities import HealthFitnessStatus, HealthRecord, HealthRecordType

    client, seed = workplace_client
    with SessionLocal() as db:
        db.add(
            HealthRecord(
                company_id=seed["own_company_id"],
                employee_id=seed["own_employee_id"],
                record_type=HealthRecordType.PERIODIC_EXAM,
                examination_date=date(2026, 7, 1),
                fitness_status=HealthFitnessStatus.FIT,
                physician_name="Arşiv Hekimi",
                created_by_id=seed["manager_id"],
                deleted_at=datetime.utcnow(),
            )
        )
        db.commit()

    headers = _headers(_token(client, seed["manager_email"], seed["password"]))
    active_health = client.get(
        f"/api/v1/health-records?company_id={seed['own_company_id']}"
        f"&employee_id={seed['own_employee_id']}",
        headers=headers,
    )
    assert active_health.status_code == 200, active_health.text
    assert active_health.json() == []

    purge = client.post(
        "/api/v1/employees/bulk-purge",
        headers=headers,
        json={
            "employee_ids": [seed["own_employee_id"]],
            "company_id": seed["own_company_id"],
        },
    )
    assert purge.status_code == 200, purge.text
    body = purge.json()
    assert body["deleted"] == 0
    assert body["linked_skipped"] == 1
    assert "arşivlenmiş/geçmiş sağlık kaydı" in body["message"]
    assert "aktif sağlık listesinde gösterilmez" in body["message"]
    assert body["blocked_details"][0]["links"][0]["historical_count"] == 1

    with SessionLocal() as db:
        from app.models.entities import Employee

        assert db.get(Employee, seed["own_employee_id"]) is not None


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

    accident = client.post("/api/v1/incidents", headers=headers, json={
        **incident_payload, "company_id": own, "event_type": "is_kazasi",
    })
    assert accident.status_code == 200, accident.text
    dof_payload = {
        "finding": "Raf üzerindeki malzemeler güvenli biçimde sabitlenmelidir.",
        "corrective_action": "Raflara koruyucu bariyer takılacak ve malzemeler sabitlenecek.",
        "responsible_person": "İşyeri Yetkilisi",
        "preventive_action": "Raflar düzenli kontrol edilecek ve çalışanlara eğitim verilecek.",
        "term_date": date.today().isoformat(),
    }
    dof = client.post(f"/api/v1/incidents/{incident.json()['id']}/dofs", headers=headers, json=dof_payload)
    assert dof.status_code == 200, dof.text
    assert client.post(f"/api/v1/incidents/{foreign_incident.json()['id']}/dofs", headers=headers, json={
        **dof_payload, "finding": "Başka işyerine yetkisiz işlem denemesi yapılmaktadır.",
    }).status_code == 403
    summary = client.get("/api/v1/workplace-portal/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["company_id"] == own
    assert summary.json()["counts"]["employees"] == 2
    assert summary.json()["counts"]["capa"] == 1
    assert summary.json()["counts"]["nearMiss"] == 1
    assert summary.json()["counts"]["accidents"] == 1
    assert client.get("/api/v1/workplace-portal/summary", headers=headers, params={"company_id": foreign}).status_code == 403

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

    committee_meta = client.get("/api/v1/ohs-committee/meta", headers=headers)
    assert committee_meta.status_code == 200, committee_meta.text
    candidates = client.get("/api/v1/ohs-committee/candidates", headers=headers, params={"company_id": own})
    assert candidates.status_code == 200, candidates.text
    meeting = client.post("/api/v1/ohs-committee/meetings/validated", headers=headers, json={
        "company_id": own, "meeting_date": date.today().isoformat(), "title": "İşyeri kurul toplantısı",
    })
    assert meeting.status_code == 201, meeting.text
    assert client.post("/api/v1/ohs-committee/meetings/validated", headers=headers, json={
        "company_id": foreign, "meeting_date": date.today().isoformat(),
    }).status_code == 403
    assert client.get(
        "/api/v1/ohs-committee/candidates",
        headers=headers,
        params={"company_id": foreign},
    ).status_code == 403
    capa_board = client.get("/api/v1/incidents/capa-board.xlsx", headers=headers)
    assert capa_board.status_code == 200, capa_board.text


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


@pytest.mark.parametrize("account_key", ["osgb_admin_email"])
def test_osgb_admin_does_not_gain_workplace_only_register_access(
    workplace_client,
    account_key,
):
    client, seed = workplace_client
    own = seed["own_company_id"]
    token = _token(client, seed[account_key], seed["password"])
    headers = _headers(token)

    assert client.get("/api/v1/sds", headers=headers).status_code == 403
    assert client.get("/api/v1/periodic-controls", headers=headers).status_code == 403
    assert client.get("/api/v1/workplace-measurements", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/sds",
        headers=headers,
        json={"company_id": own, "product_name": "Yetkisiz Ürün"},
    ).status_code == 403
