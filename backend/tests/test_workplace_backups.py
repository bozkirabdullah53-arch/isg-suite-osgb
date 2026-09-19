from datetime import datetime, timedelta
from io import BytesIO
from zipfile import ZipFile
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
        with ZipFile(BytesIO(response.content)) as archive:
            assert "Yedek Raporu.html" in archive.namelist()
    finally:
        app.dependency_overrides.clear()

def test_backup_contains_safe_offline_printable_turkish_report(setup):
    from app.services.workplace_backup import create_company_backup
    from app.services.archive_store import resolve_archive_path
    from app.models.entities import BackupSource
    factory, (own, _foreign, _user_id) = setup
    with factory() as db:
        db.get(Company, own).name = '<script>alert("x")</script> Test İşyeri'
        db.commit()
        row = create_company_backup(
            db,
            company_id=own,
            actor_user_id=None,
            source=BackupSource.MANUAL,
        )
        backup_bytes = resolve_archive_path(row).read_bytes()

    with ZipFile(BytesIO(backup_bytes)) as archive:
        assert "Yedek Raporu.html" in archive.namelist()
        report = archive.read("Yedek Raporu.html").decode("utf-8")

    assert "İşyeri Yedek Raporu" in report
    assert "Yazdır / PDF Kaydet" in report
    assert "Çalışanlar" in report
    assert "window.print()" in report
    assert '<script>alert("x")</script>' not in report
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; Test İşyeri" in report


def test_cleanup_removes_only_stale_failed_records_and_partial_files(setup):
    import os
    from app.models.entities import ArchiveKind, BackupSource, BackupStatus
    from app.services.archive_store import archive_root
    from app.services.workplace_backup import cleanup_incomplete_workplace_backups

    factory, (own, _foreign, _user_id) = setup
    backups = archive_root() / "backups" / f"company-{own}"
    backups.mkdir(parents=True, exist_ok=True)
    stale_partial = backups / ".partial-stale.zip"
    stale_partial.write_bytes(b"stale")
    old_timestamp = (datetime.utcnow() - timedelta(hours=2)).timestamp()
    os.utime(stale_partial, (old_timestamp, old_timestamp))

    completed_path = backups / "keep.zip"
    completed_path.write_bytes(b"keep")
    with factory() as db:
        failed = EisaArchiveRecord(
            kind=ArchiveKind.TENANT_BACKUP,
            company_id=own,
            entity_type="workplace_backup_v4",
            storage_path=f"backups/company-{own}/failed.zip",
            size_bytes=0,
            backup_source=BackupSource.MANUAL,
            backup_status=BackupStatus.FAILED,
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        completed = EisaArchiveRecord(
            kind=ArchiveKind.TENANT_BACKUP,
            company_id=own,
            entity_type="workplace_backup_v4",
            storage_path=f"backups/company-{own}/keep.zip",
            size_bytes=4,
            backup_source=BackupSource.MANUAL,
            backup_status=BackupStatus.COMPLETED,
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        db.add_all([failed, completed])
        db.commit()
        failed_id, completed_id = failed.id, completed.id

        summary = cleanup_incomplete_workplace_backups(db)

        assert summary["deleted_rows"] == 1
        assert summary["deleted_partial_files"] == 1
        assert db.get(EisaArchiveRecord, failed_id) is None
        assert db.get(EisaArchiveRecord, completed_id) is not None

    assert not stale_partial.exists()
    assert completed_path.exists()


def test_backup_fails_cleanly_when_disk_is_full(setup, monkeypatch):
    from app.services import workplace_backup
    from app.services.workplace_backup import BackupStorageFullError, create_company_backup
    from app.models.entities import BackupSource, BackupStatus, EisaArchiveRecord

    factory, (own, _foreign, _user_id) = setup

    class FullDisk:
        free = 0

    monkeypatch.setattr(workplace_backup.shutil, "disk_usage", lambda _path: FullDisk())

    with factory() as db:
        with pytest.raises(BackupStorageFullError):
            create_company_backup(
                db,
                company_id=own,
                actor_user_id=None,
                source=BackupSource.MANUAL,
            )
        row = db.scalars(
            select(EisaArchiveRecord)
            .where(EisaArchiveRecord.company_id == own)
            .order_by(EisaArchiveRecord.id.desc())
        ).first()
        assert row is not None
        assert row.backup_status == BackupStatus.FAILED
        assert "depolama alanı" in (row.error_summary or "")


class _FakeRemoteBackupStore:
    def __init__(self):
        self.objects = {}

    def remote_size(self, key):
        content = self.objects.get(key)
        return None if content is None else len(content)

    def put_file(self, key, path, *, content_type=None):
        self.objects[key] = path.read_bytes()
        return key

    def iter_range(self, key, *, start, end):
        yield self.objects[key][start:end + 1]

    def get_range(self, key, *, start, end):
        return self.objects[key][start:end + 1]

    def delete(self, key):
        self.objects.pop(key, None)


def test_completed_workplace_backup_moves_to_remote_only_after_checksum_verification(setup, monkeypatch):
    import hashlib
    from app.core.config import settings
    from app.models.entities import ArchiveKind, BackupSource, BackupStatus
    from app.services import workplace_backup
    from app.services.archive_store import archive_root

    factory, (own, _foreign, _user_id) = setup
    remote = _FakeRemoteBackupStore()
    monkeypatch.setattr(settings, "workplace_backup_remote_enabled", True)
    monkeypatch.setattr(workplace_backup, "_remote_backup_store", lambda: remote)

    local = archive_root() / "backups" / f"company-{own}" / "remote-test.zip"
    local.parent.mkdir(parents=True, exist_ok=True)
    payload = b"verified remote workplace backup"
    local.write_bytes(payload)
    with factory() as db:
        row = EisaArchiveRecord(
            kind=ArchiveKind.TENANT_BACKUP,
            company_id=own,
            entity_type="workplace_backup_v4",
            storage_path=str(local.relative_to(archive_root())).replace("\\", "/"),
            size_bytes=len(payload),
            checksum=hashlib.sha256(payload).hexdigest(),
            backup_source=BackupSource.MANUAL,
            backup_status=BackupStatus.COMPLETED,
        )
        db.add(row)
        db.commit()

        summary = workplace_backup.migrate_completed_workplace_backups(db)

    assert summary["migrated"] == 1
    assert summary["bytes_freed"] == len(payload)
    assert not local.exists()
    assert remote.objects["workplace-backups/backups/company-%s/remote-test.zip" % own] == payload


def test_remote_only_workplace_backup_can_be_read_as_manifest(setup, monkeypatch):
    import hashlib
    import json
    from app.core.config import settings
    from app.models.entities import ArchiveKind, BackupSource, BackupStatus
    from app.services import workplace_backup

    factory, (own, _foreign, _user_id) = setup
    remote = _FakeRemoteBackupStore()
    monkeypatch.setattr(settings, "workplace_backup_remote_enabled", True)
    monkeypatch.setattr(workplace_backup, "_remote_backup_store", lambda: remote)

    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"company_id": own, "format_version": 4}))
    payload = buffer.getvalue()
    storage_path = f"backups/company-{own}/remote-only.zip"
    remote.objects[f"workplace-backups/{storage_path}"] = payload
    row = EisaArchiveRecord(
        kind=ArchiveKind.TENANT_BACKUP,
        company_id=own,
        entity_type="workplace_backup_v4",
        storage_path=storage_path,
        size_bytes=len(payload),
        checksum=hashlib.sha256(payload).hexdigest(),
        backup_source=BackupSource.MANUAL,
        backup_status=BackupStatus.COMPLETED,
    )

    with factory() as db:
        manifest = workplace_backup.read_company_backup_manifest(row)

    assert manifest == {"company_id": own, "format_version": 4}
