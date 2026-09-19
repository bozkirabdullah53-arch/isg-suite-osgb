from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.models.entities import Company, EisaArchiveRecord, User, UserRole

@pytest.fixture()
def setup(tmp_path, monkeypatch):
    from app.core.config import settings
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine); factory = sessionmaker(bind=engine)
    with factory() as db:
        a, b = Company(name="A", is_active=True), Company(name="B", is_active=True); db.add_all([a,b]); db.flush()
        user = User(email="manager@example.com", full_name="Manager", hashed_password="x", role=UserRole.COMPANY_ADMIN, company_id=a.id, is_active=True)
        db.add(user); db.commit(); db.refresh(user); ids=(a.id,b.id,user.id)
    monkeypatch.setattr(settings, "workplace_backups_enabled", True); monkeypatch.setattr(settings, "workplace_backups_force_off", False)
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path/"backups")); monkeypatch.setattr(settings, "upload_dir", str(tmp_path/"uploads"))
    return factory, ids

def test_api_uses_authenticated_company_and_hides_foreign(setup):
    from app.main import app
    from app.api.deps import get_current_user
    factory, (own, foreign, user_id) = setup
    def db_dep():
        with factory() as db: yield db
    def user_dep():
        with factory() as db: return db.get(User, user_id)
    app.dependency_overrides[get_db] = db_dep; app.dependency_overrides[get_current_user] = user_dep
    try:
        client=TestClient(app); made=client.post("/api/v1/workplace-backups", json={})
        assert made.status_code == 200 and made.json()["company_id"] == own
        with factory() as db:
            foreign_row=EisaArchiveRecord(kind="tenant_backup", company_id=foreign, entity_type="workplace_backup_v4", storage_path="missing.zip", size_bytes=0)
            db.add(foreign_row); db.commit(); foreign_id=foreign_row.id
        assert client.get(f"/api/v1/workplace-backups/{foreign_id}/download").status_code == 404
        assert client.post("/api/v1/workplace-backups", json={"company_id": foreign}).status_code == 422
    finally: app.dependency_overrides.clear()

def test_scheduler_is_idempotent(setup):
    from app.services.workplace_backup import run_scheduled_company_backups
    factory, _ = setup; now=datetime(2026,9,18,23)
    first=run_scheduled_company_backups(factory, now=now); second=run_scheduled_company_backups(factory, now=now+timedelta(minutes=5))
    assert first.created == 2 and second.skipped == 2 and second.created == 0
    with factory() as db: assert len(db.scalars(select(EisaArchiveRecord)).all()) == 2

def test_qr_workplace_account_can_access_only_own_backups(setup):
    from app.main import app
    from app.api.deps import get_current_user
    factory, (own, _foreign, user_id) = setup
    with factory() as db:
        db.get(User, user_id).email = "isyeri.1@kiosk.isgsuite.tr"
        db.commit()
    def db_dep():
        with factory() as db: yield db
    def user_dep():
        with factory() as db: return db.get(User, user_id)
    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[get_current_user] = user_dep
    try:
        response = TestClient(app).get("/api/v1/workplace-backups")
        assert response.status_code == 200
        assert all(row["company_id"] == own for row in response.json())
    finally:
        app.dependency_overrides.clear()

def test_encrypted_backup_downloads_as_offline_openable_zip(setup, monkeypatch):
    from app.main import app
    from app.api.deps import get_current_user
    from app.core.config import settings
    factory, (_own, _foreign, user_id) = setup
    monkeypatch.setattr(settings, "backup_encryption_key", "test-backup-key-with-at-least-32-characters")
    def db_dep():
        with factory() as db: yield db
    def user_dep():
        with factory() as db: return db.get(User, user_id)
    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[get_current_user] = user_dep
    try:
        client = TestClient(app)
        created = client.post("/api/v1/workplace-backups", json={}).json()
        with factory() as db:
            stored = db.get(EisaArchiveRecord, created["id"])
            assert stored.original_name.endswith(".zip.enc")
        response = client.get(f"/api/v1/workplace-backups/{created['id']}/download")
        assert response.status_code == 200
        assert response.content.startswith(b"PK")
        assert ".zip.enc" not in response.headers["content-disposition"]
        assert ".zip" in response.headers["content-disposition"]
    finally:
        app.dependency_overrides.clear()
