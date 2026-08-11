"""OSGB kalıcı silme — bağlı FK engelleri için regresyon testleri."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "osgb_purge.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent
    # Dijital personel kartı tablolarını test metadata'sına kaydet.
    import app.models.personnel_profile  # noqa: F401
    import app.models.personnel_profile_document  # noqa: F401
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"

    engine = create_engine(url, connect_args={"check_same_thread": False})

    # SQLite testinde de production PostgreSQL'deki RESTRICT FK davranışını gerçekten
    # uygulayalım; aksi halde bu regresyon testi hatalı silme sırasını yakalayamaz.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)
    # Bu üç kurul alt tablosu migration'larla gelir, ORM metadata'sında yoktur.
    # OSGB purge akışı şirket FK'larını silmeden önce bunları doğrudan temizler.
    with engine.begin() as connection:
        for table in (
            "ohs_committee_signature_steps",
            "ohs_committee_meeting_versions",
            "ohs_committee_duplicate_reports",
        ):
            connection.exec_driver_sql(
                f"CREATE TABLE IF NOT EXISTS {table} ("
                "id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL)"
            )

    from app.main import app

    return TestClient(app)


def test_purge_osgb_deletes_despite_dry_run_logs(client: TestClient):
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import IntegrationDryRunLog, OsgbOrganization, User, UserRole
    from app.services.osgb_purge import purge_osgb

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="ASD Purge",
            authorization_number="YETKI-PURGE-1",
            tax_number="1122334455",
            responsible_manager="Test",
            email="purge-osgb@test.com",
            phone="02120000000",
            address="Istanbul",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        osgb_id = osgb.id
        db.add(
            User(
                email="ga-purge@test.com",
                full_name="Global Admin",
                hashed_password=get_password_hash("Test1234!"),
                role=UserRole.GLOBAL_ADMIN,
                is_active=True,
            )
        )
        db.add(
            IntegrationDryRunLog(
                user_email="expert@test.com",
                osgb_id=osgb_id,
                adapter="ibys",
                status="dry_run",
                record_count=3,
            )
        )
        db.commit()

    with SessionLocal() as db:
        name = purge_osgb(db, osgb_id)
        db.commit()
        assert name == "ASD Purge"
        assert db.get(OsgbOrganization, osgb_id) is None
        from sqlalchemy import select

        left = db.scalars(
            select(IntegrationDryRunLog).where(IntegrationDryRunLog.osgb_id == osgb_id)
        ).all()
        assert left == []


def test_purge_osgb_removes_assignments_and_health_access_logs(client: TestClient):
    """OSGB silinince atamalar ve şirket FK'sı taşıyan sağlık erişim kayıtları kalkar."""
    from datetime import date

    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        HealthAccessLog,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        User,
        UserRole,
        WorkplaceAssignment,
    )
    from app.services.osgb_purge import purge_osgb

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Assignment Purge OSGB",
            authorization_number="YETKI-ASG-PURGE-1",
            tax_number="8877665544",
            responsible_manager="Test",
            email="assignment-purge@test.com",
            phone="02125556677",
            address="Bursa",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Assignment Purge Company",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Çok Tehlikeli",
        )
        professional = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Purge Uzmanı",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            is_active=True,
        )
        user = User(
            email="assignment-purge-user@test.com",
            full_name="Purge Kullanıcısı",
            hashed_password=get_password_hash("Test1234!"),
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add_all([company, professional, user])
        db.flush()
        assignment = WorkplaceAssignment(
            osgb_id=osgb.id,
            company_id=company.id,
            professional_id=professional.id,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            start_date=date(2026, 1, 1),
            status=AssignmentStatus.ACTIVE,
        )
        access_log = HealthAccessLog(
            company_id=company.id,
            actor_user_id=user.id,
            action="view",
            entry_hash="assignment-purge-health-access-log",
        )
        db.add_all([assignment, access_log])
        db.commit()
        osgb_id = osgb.id
        company_id = company.id
        assignment_id = assignment.id
        access_log_id = access_log.id

    with SessionLocal() as db:
        name = purge_osgb(db, osgb_id)
        db.commit()
        assert name == "Assignment Purge OSGB"
        assert db.get(OsgbOrganization, osgb_id) is None
        assert db.get(Company, company_id) is None
        assert db.get(WorkplaceAssignment, assignment_id) is None
        assert db.get(HealthAccessLog, access_log_id) is None


def test_purge_osgb_disables_linked_accounts_and_invalidates_sessions(client: TestClient):
    """OSGB silinince yönetici, kiosk ve üyelikten bağlı hesaplar giriş yapamaz."""
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        Company,
        OrganizationMembership,
        OsgbOrganization,
        User,
        UserRole,
    )
    from app.services.osgb_purge import purge_osgb

    password = "Test1234!"
    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Account Purge OSGB",
            authorization_number="YETKI-ACCOUNT-PURGE-1",
            tax_number="7766554433",
            responsible_manager="Test",
            email="account-purge@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Account Purge Company",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Az Tehlikeli",
        )
        db.add(company)
        db.flush()

        osgb_admin = User(
            email="account-admin@test.com",
            full_name="OSGB Yönetici",
            hashed_password=get_password_hash(password),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            is_active=True,
        )
        kiosk = User(
            email="account-kiosk@test.com",
            full_name="İşyeri Kiosk",
            hashed_password=get_password_hash(password),
            role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id,
            company_id=company.id,
            is_active=True,
        )
        legacy_kiosk = User(
            email="legacy-kiosk@test.com",
            full_name="Eski Kiosk",
            hashed_password=get_password_hash(password),
            role=UserRole.COMPANY_ADMIN,
            company_id=company.id,
            is_active=True,
        )
        membership_user = User(
            email="membership-user@test.com",
            full_name="Üyelik Kullanıcısı",
            hashed_password=get_password_hash(password),
            role=UserRole.SAFETY_SPECIALIST,
            is_active=True,
        )
        db.add_all([osgb_admin, kiosk, legacy_kiosk, membership_user])
        db.flush()
        db.add(
            OrganizationMembership(
                user_id=membership_user.id,
                osgb_id=osgb.id,
                role=UserRole.SAFETY_SPECIALIST.value,
                is_active=True,
            )
        )
        db.commit()

        osgb_id = osgb.id
        account_ids = [
            osgb_admin.id,
            kiosk.id,
            legacy_kiosk.id,
            membership_user.id,
        ]
        old_token_version = osgb_admin.token_version

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "account-admin@test.com", "password": password},
    )
    assert login.status_code == 200, login.text
    old_token = login.json()["access_token"]

    with SessionLocal() as db:
        assert purge_osgb(db, osgb_id) == "Account Purge OSGB"
        db.commit()

    with SessionLocal() as db:
        accounts = [db.get(User, account_id) for account_id in account_ids]
        assert all(account is not None for account in accounts)
        assert all(account.is_active is False for account in accounts)
        assert all(account.osgb_id is None for account in accounts)
        assert all(account.company_id is None for account in accounts)
        assert db.get(User, account_ids[0]).token_version > old_token_version

    # Mevcut access token da pasif hesap/token_version kontrolünde düşmelidir.
    blocked_session = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert blocked_session.status_code == 401

    for email in (
        "account-admin@test.com",
        "account-kiosk@test.com",
        "legacy-kiosk@test.com",
        "membership-user@test.com",
    ):
        blocked_login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert blocked_login.status_code == 401


def test_purge_osgb_deletes_inactive_employee_personnel_profile(client: TestClient):
    """P0 regresyon: UI'da silinen/pasif personelin profil FK'sı OSGB silmeyi engellemesin."""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.entities import Company, Employee, OsgbOrganization
    from app.models.personnel_profile import PersonnelProfile, PersonnelProfileContact
    from app.services.osgb_purge import purge_osgb

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Profile Purge OSGB",
            authorization_number="YETKI-PP-1",
            tax_number="4433221100",
            responsible_manager="Test",
            email="profile-purge@test.com",
            phone="02124445566",
            address="Bursa",
            is_active=False,
        )
        db.add(osgb)
        db.flush()
        company = Company(
            name="Profile Purge Company",
            osgb_id=osgb.id,
            is_active=True,
            hazard_class="Az Tehlikeli",
        )
        db.add(company)
        db.flush()
        employee = Employee(
            company_id=company.id,
            full_name="Pasif Personel",
            national_id_masked="***********",
            is_active=False,
        )
        db.add(employee)
        db.flush()
        profile = PersonnelProfile(
            osgb_id=osgb.id,
            company_id=company.id,
            subject_type="employee",
            employee_id=employee.id,
            status="archived",
        )
        db.add(profile)
        db.flush()
        db.add(
            PersonnelProfileContact(
                profile_id=profile.id,
                company_id=company.id,
                entry_key="00000000-0000-0000-0000-000000000001",
                version=1,
                contact_type="corporate_email",
                contact_value="pasif@example.com",
                lifecycle_status="archived",
            )
        )
        db.commit()
        osgb_id = osgb.id
        company_id = company.id
        employee_id = employee.id
        profile_id = profile.id

    with SessionLocal() as db:
        name = purge_osgb(db, osgb_id)
        db.commit()
        assert name == "Profile Purge OSGB"
        assert db.get(OsgbOrganization, osgb_id) is None
        assert db.get(Company, company_id) is None
        assert db.get(Employee, employee_id) is None
        assert db.get(PersonnelProfile, profile_id) is None
        contacts = db.scalars(
            select(PersonnelProfileContact).where(PersonnelProfileContact.profile_id == profile_id)
        ).all()
        assert contacts == []


def test_purge_company_with_emergency_teams(client: TestClient):
    """P0 regresyon: emergency_teams FK firma silmeyi engellemesin."""
    from app.api.companies import _purge_company_data
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        Company,
        EmergencyTeam,
        EmergencyTeamType,
        OsgbOrganization,
        User,
        UserRole,
    )
    from sqlalchemy import select

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="VoLor Purge OSGB",
            authorization_number="YETKI-EM-1",
            tax_number="9988776655",
            responsible_manager="Test",
            email="em-purge@test.com",
            phone="02121112233",
            address="Ankara",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(name="VoLorBoZ", osgb_id=osgb.id, is_active=True, hazard_class="Az Tehlikeli")
        db.add(company)
        db.flush()
        admin = User(
            email="em-admin@test.com",
            full_name="Admin",
            hashed_password=get_password_hash("Test1234!"),
            role=UserRole.COMPANY_ADMIN,
            company_id=company.id,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        ttype = EmergencyTeamType(
            company_id=company.id,
            code="sondurme",
            name="Sondurme",
            is_system=False,
            min_members=2,
        )
        db.add(ttype)
        db.flush()
        db.add(
            EmergencyTeam(
                company_id=company.id,
                type_id=ttype.id,
                name="Ekip A",
                min_members=2,
                created_by_id=admin.id,
            )
        )
        db.commit()
        cid = company.id

    with SessionLocal() as db:
        _purge_company_data(db, cid)
        db.delete(db.get(Company, cid))
        db.commit()
        assert db.get(Company, cid) is None
        left = db.scalars(select(EmergencyTeam).where(EmergencyTeam.company_id == cid)).all()
        assert left == []
