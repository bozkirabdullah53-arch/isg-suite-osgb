"""OSGB kalıcı silme — integration_dry_run_logs FK engeli regresyonu."""
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

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

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
