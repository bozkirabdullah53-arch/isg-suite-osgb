"""Merkezi arşiv: silme öncesi kopya + yol güvenliği."""
from pathlib import Path
from types import SimpleNamespace

from app.models.entities import ArchiveKind, User, UserRole
from app.services import archive_store


class _FakeDB:
    def __init__(self):
        self.added = []

    def get(self, *_a, **_k):
        return None

    def add(self, row):
        self.added.append(row)

    def flush(self):
        for i, row in enumerate(self.added, start=1):
            if getattr(row, "id", None) is None:
                row.id = i


def test_archive_file_before_delete_copies_and_records(tmp_path, monkeypatch):
    backup = tmp_path / "backups"
    uploads = tmp_path / "uploads"
    backup.mkdir()
    uploads.mkdir()
    src = uploads / "doc.pdf"
    src.write_bytes(b"%PDF-1.4 archived")

    monkeypatch.setattr(archive_store.settings, "backup_dir", str(backup))
    monkeypatch.setattr(archive_store.settings, "upload_dir", str(uploads))

    user = User(
        id=1,
        email="admin@osgb.test",
        full_name="Admin",
        hashed_password="x",
        role=UserRole.COMPANY_ADMIN,
        company_id=10,
        osgb_id=3,
    )
    db = _FakeDB()
    row = archive_store.archive_file_before_delete(
        db,
        source=src,
        user=user,
        company_id=10,
        osgb_id=3,
        entity_type="document",
        entity_id="99",
        original_name="rapor.pdf",
        notes="test",
    )
    assert row is not None
    assert row.kind == ArchiveKind.DELETED_FILE
    assert row.original_name == "rapor.pdf"
    assert row.osgb_id == 3
    assert row.company_id == 10
    stored = archive_store.resolve_archive_path(row)
    assert stored.exists()
    assert stored.read_bytes() == b"%PDF-1.4 archived"
    assert src.exists()  # kaynak henüz silinmedi; arşiv kopyadır


def test_archive_missing_source_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(archive_store.settings, "backup_dir", str(tmp_path / "b"))
    db = _FakeDB()
    assert (
        archive_store.archive_file_before_delete(
            db,
            source=tmp_path / "yok.pdf",
            user=None,
            company_id=1,
            entity_type="x",
            entity_id="1",
        )
        is None
    )


def test_create_tenant_backup_zip(tmp_path, monkeypatch):
    backup = tmp_path / "backups"
    uploads = tmp_path / "uploads"
    company_dir = uploads / "10"
    company_dir.mkdir(parents=True)
    (company_dir / "a.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setattr(archive_store.settings, "backup_dir", str(backup))
    monkeypatch.setattr(archive_store.settings, "upload_dir", str(uploads))

    company = SimpleNamespace(id=10, name="Firma A", osgb_id=3)
    user = User(
        id=1,
        email="admin@osgb.test",
        full_name="Admin",
        hashed_password="x",
        role=UserRole.COMPANY_ADMIN,
        company_id=10,
        osgb_id=3,
    )

    class DB:
        def get(self, model, pk):
            if pk == 10:
                return company
            if pk == 3:
                return SimpleNamespace(name="OSGB X")
            return None

        def scalars(self, _stmt):
            return SimpleNamespace(all=lambda: [])

        def add(self, row):
            self.row = row

        def commit(self):
            pass

        def refresh(self, row):
            row.id = 1

    row = archive_store.create_tenant_backup(DB(), user=user, company_id=10)
    assert row.kind == ArchiveKind.TENANT_BACKUP
    path = archive_store.resolve_archive_path(row)
    assert path.suffix == ".zip"
    assert path.stat().st_size > 0
