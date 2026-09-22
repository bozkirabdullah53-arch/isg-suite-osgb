"""İşyeri yedeği denetim kayıtları ve yedek sağlık durumu."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.entities import (
    ArchiveKind,
    AuditLog,
    BackupSource,
    BackupStatus,
    Company,
    EisaArchiveRecord,
    User,
    UserRole,
)


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    from app.core.config import settings

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        company = Company(name="A", is_active=True)
        db.add(company)
        db.flush()
        user = User(
            email="manager@example.com",
            full_name="Manager",
            hashed_password="x",
            role=UserRole.COMPANY_ADMIN,
            company_id=company.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        ids = (company.id, user.id)

    monkeypatch.setattr(settings, "workplace_backups_enabled", True)
    monkeypatch.setattr(settings, "workplace_backups_force_off", False)
    monkeypatch.setattr(settings, "workplace_backup_remote_enabled", False)
    monkeypatch.setattr(settings, "workplace_backup_remote_prefix", "workplace-backups")
    monkeypatch.setattr(settings, "backup_encryption_key", "")
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    monkeypatch.setattr(settings, "backup_encryption_force_off", False)
    monkeypatch.setattr(settings, "backup_remote_enabled", False)
    monkeypatch.setattr(settings, "backup_remote_required", False)
    monkeypatch.setattr(settings, "backup_max_age_hours", 36)
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    return factory, ids


def _client(factory, user_id):
    from app.api.deps import get_current_user
    from app.main import app

    def db_dep():
        with factory() as db:
            yield db

    def user_dep():
        with factory() as db:
            return db.get(User, user_id)

    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[get_current_user] = user_dep
    return app, TestClient(app)


def _audits(factory, action: str) -> list[AuditLog]:
    with factory() as db:
        return list(
            db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)).all()
        )


def test_manual_backup_writes_audit_row(setup):
    factory, (company_id, user_id) = setup
    app, client = _client(factory, user_id)
    try:
        response = client.post("/api/v1/workplace-backups", json={})
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()

    rows = _audits(factory, "workplace_backup_created")
    assert len(rows) == 1
    assert rows[0].company_id == company_id
    assert rows[0].module == "backup"
    assert rows[0].entity_id == str(response.json()["id"])
    assert rows[0].new_value and "checksum" in rows[0].new_value


def test_contents_endpoint_returns_checksum_and_audits(setup):
    factory, (company_id, user_id) = setup
    app, client = _client(factory, user_id)
    try:
        created = client.post("/api/v1/workplace-backups", json={})
        assert created.status_code == 200
        backup_id = created.json()["id"]
        response = client.get(f"/api/v1/workplace-backups/{backup_id}/contents")
        assert response.status_code == 200, response.text
        assert response.json()["checksum"] == "verified"
        assert response.json()["manifest"]["company_id"] == company_id
    finally:
        app.dependency_overrides.clear()

    assert len(_audits(factory, "workplace_backup_inspected")) == 1


def test_download_writes_audit_row(setup):
    factory, (_company_id, user_id) = setup
    app, client = _client(factory, user_id)
    try:
        created = client.post("/api/v1/workplace-backups", json={})
        backup_id = created.json()["id"]
        response = client.get(f"/api/v1/workplace-backups/{backup_id}/download")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()

    assert len(_audits(factory, "workplace_backup_downloaded")) == 1


def test_status_reports_backup_health(setup):
    factory, (_company_id, user_id) = setup
    app, client = _client(factory, user_id)
    try:
        created = client.post("/api/v1/workplace-backups", json={})
        assert created.status_code == 200
        status = client.get("/api/v1/workplace-backups/status")
        assert status.status_code == 200
        payload = status.json()
    finally:
        app.dependency_overrides.clear()

    assert payload["healthy"] is True
    assert payload["last_successful_backup_at"] is not None
    assert payload["backup_age_hours"] is not None
    assert payload["failed_count"] == 0
    assert payload["max_age_hours"] == 36


def test_status_unhealthy_without_backup(setup):
    factory, (_company_id, user_id) = setup
    app, client = _client(factory, user_id)
    try:
        payload = client.get("/api/v1/workplace-backups/status").json()
    finally:
        app.dependency_overrides.clear()

    assert payload["healthy"] is False
    assert payload["last_successful_backup_at"] is None
    assert payload["failed_count"] == 0


def test_purge_writes_audit_row(setup, monkeypatch):
    from app.core.config import settings
    from app.services.workplace_backup import purge_expired_scheduled_backups

    factory, (company_id, _user_id) = setup
    from app.services.archive_store import archive_root

    target = archive_root() / "backups" / f"company-{company_id}" / "old.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"zip-bytes")

    with factory() as db:
        row = EisaArchiveRecord(
            kind=ArchiveKind.TENANT_BACKUP,
            company_id=company_id,
            entity_type="workplace_backup_v4",
            entity_id=str(company_id),
            original_name="old.zip",
            storage_path=f"backups/company-{company_id}/old.zip",
            size_bytes=9,
            checksum="a" * 64,
            backup_source=BackupSource.SCHEDULED,
            backup_status=BackupStatus.COMPLETED,
            completed_at=datetime.utcnow() - timedelta(days=90),
        )
        db.add(row)
        db.commit()

        summary = purge_expired_scheduled_backups(db, cutoff=datetime.utcnow() - timedelta(days=30))

    assert summary.deleted == 1
    rows = _audits(factory, "workplace_backup_purged")
    assert len(rows) == 1
    assert rows[0].company_id == company_id
    assert rows[0].old_value and "retention_cutoff" in rows[0].old_value
    assert target.exists() is False


def test_manual_backups_are_not_purged(setup):
    from app.services.workplace_backup import purge_expired_scheduled_backups

    factory, (company_id, _user_id) = setup
    from app.services.archive_store import archive_root

    target = archive_root() / "backups" / f"company-{company_id}" / "manual.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"zip-bytes")

    with factory() as db:
        row = EisaArchiveRecord(
            kind=ArchiveKind.TENANT_BACKUP,
            company_id=company_id,
            entity_type="workplace_backup_v4",
            entity_id=str(company_id),
            original_name="manual.zip",
            storage_path=f"backups/company-{company_id}/manual.zip",
            size_bytes=9,
            checksum="a" * 64,
            backup_source=BackupSource.MANUAL,
            backup_status=BackupStatus.COMPLETED,
            completed_at=datetime.utcnow() - timedelta(days=900),
        )
        db.add(row)
        db.commit()
        summary = purge_expired_scheduled_backups(db, cutoff=datetime.utcnow() - timedelta(days=30))

    assert summary.deleted == 0
    assert target.exists() is True


def test_scheduled_failure_creates_admin_notification(setup, monkeypatch):
    from app.models.entities import Notification, NotificationType
    from app.services import workplace_backup as wb

    factory, (company_id, _user_id) = setup
    with factory() as db:
        db.add(
            User(
                email="root@example.com",
                full_name="Root",
                hashed_password="x",
                role=UserRole.GLOBAL_ADMIN,
                is_active=True,
            )
        )
        db.commit()

    def _boom(*args, **kwargs):
        raise RuntimeError("disk hatası")

    monkeypatch.setattr(wb, "create_company_backup", _boom)
    summary = wb.run_scheduled_company_backups(factory, now=datetime(2026, 9, 21, 2, 0, 0))

    assert summary.failed >= 1
    with factory() as db:
        rows = list(
            db.scalars(
                select(Notification).where(
                    Notification.type == NotificationType.CRITICAL,
                    Notification.entity_type == "backup_failure",
                )
            ).all()
        )
    assert rows
    assert "başarısız" in rows[0].title.lower()


def test_audit_helper_serializes_values():
    from app.services.audit import serialize_audit_value

    assert serialize_audit_value({"a": 1}) == '{"a": 1}'
    assert serialize_audit_value(None) is None
    long_value = serialize_audit_value("x" * 30_000)
    assert long_value is not None
    assert long_value.endswith("…[kısaltıldı]")
