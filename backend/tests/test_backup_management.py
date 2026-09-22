"""Yedek yönetimi — GFS saklama, offsite doğrulama ve RPO durumu."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from app.core.config import settings
from app.services import backup_management as bm

NOW = datetime(2026, 9, 21, 3, 0, 0)


@pytest.fixture()
def backup_dir(tmp_path, monkeypatch):
    root = tmp_path / "backups"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "backup_dir", str(root))
    monkeypatch.setattr(settings, "db_backup_retention_days", 30)
    monkeypatch.setattr(settings, "db_backup_weekly_retention_weeks", 12)
    monkeypatch.setattr(settings, "db_backup_monthly_retention_months", 12)
    monkeypatch.setattr(settings, "backup_max_age_hours", 36)
    monkeypatch.setattr(settings, "backup_remote_enabled", False)
    monkeypatch.setattr(settings, "backup_remote_required", False)
    monkeypatch.setattr(settings, "backup_remote_prefix", "db-backups")
    monkeypatch.setattr(settings, "db_backup_enabled", True)
    return root


def _dump(root: Path, stamp: str, *, suffix: str = ".dump") -> Path:
    path = root / f"isgsuite-{stamp}{suffix}"
    path.write_bytes(b"dump-" + stamp.encode())
    return path


class _FakeRemote:
    """put_file + remote_size + iter_range + delete davranışını taklit eder."""

    def __init__(self, *, corrupt: bool = False) -> None:
        self.objects: dict[str, bytes] = {}
        self.corrupt = corrupt
        self.deleted: list[str] = []

    def put_file(self, key: str, path: Path, *, content_type: str | None = None) -> str:
        payload = Path(path).read_bytes()
        if self.corrupt:
            payload = payload + b"X"
        self.objects[key] = payload
        return key

    def remote_size(self, key: str) -> int | None:
        payload = self.objects.get(key)
        return len(payload) if payload is not None else None

    def iter_range(self, key: str, *, start: int, end: int):
        payload = self.objects.get(key)
        if payload is None:
            return
        yield payload[start : end + 1]

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)


# --- Saklama (retention) ---------------------------------------------------


def test_daily_window_keeps_all_recent(backup_dir):
    paths = [_dump(backup_dir, "20260919-030000"), _dump(backup_dir, "20260920-030000"), _dump(backup_dir, "20260921-030000")]
    summary = bm.purge_expired_database_backups(now=NOW)
    assert summary.deleted == 0
    assert all(p.exists() for p in paths)


def test_weekly_tier_keeps_only_newest_of_week(backup_dir):
    older = _dump(backup_dir, "20260727-030000")  # Pazartesi
    newer = _dump(backup_dir, "20260729-030000")  # Çarşamba (aynı ISO haftası)
    bm.purge_expired_database_backups(now=NOW)
    assert newer.exists() is True
    assert older.exists() is False


def test_monthly_tier_keeps_only_newest_of_month(backup_dir):
    older = _dump(backup_dir, "20260301-030000")
    newer = _dump(backup_dir, "20260320-030000")
    bm.purge_expired_database_backups(now=NOW)
    assert newer.exists() is True
    assert older.exists() is False


def test_beyond_monthly_window_deleted(backup_dir):
    too_old = _dump(backup_dir, "20230101-030000")
    bm.purge_expired_database_backups(now=NOW)
    assert too_old.exists() is False


def test_unknown_file_names_are_preserved(backup_dir):
    manual = backup_dir / "manual-note.txt"
    manual.write_text("korunmalı", encoding="utf-8")
    odd = backup_dir / "isgsuite-manual.dump"
    odd.write_bytes(b"x")
    bm.purge_expired_database_backups(now=NOW)
    assert manual.exists() is True
    assert odd.exists() is True


def test_other_extensions_are_ignored(backup_dir):
    other = backup_dir / "isgsuite-20200101-030000.tar.gz"
    other.write_bytes(b"x")
    bm.purge_expired_database_backups(now=NOW)
    assert other.exists() is True


def test_encrypted_names_are_classified(backup_dir):
    recent = _dump(backup_dir, "20260920-030000", suffix=".dump.enc")
    ancient = _dump(backup_dir, "20200101-030000", suffix=".dump.enc")
    bm.purge_expired_database_backups(now=NOW)
    assert recent.exists() is True
    assert ancient.exists() is False


def test_sqlite_extension_is_classified(backup_dir):
    ancient = _dump(backup_dir, "20200101-030000", suffix=".db")
    bm.purge_expired_database_backups(now=NOW)
    assert ancient.exists() is False


def test_daily_boundary_is_inclusive(backup_dir):
    boundary = _dump(backup_dir, "20260822-030000")  # tam 30 gün
    bm.purge_expired_database_backups(now=NOW)
    assert boundary.exists() is True


def test_purge_is_idempotent(backup_dir):
    _dump(backup_dir, "20200101-030000")
    assert bm.purge_expired_database_backups(now=NOW).deleted == 1
    assert bm.purge_expired_database_backups(now=NOW).deleted == 0


def test_purge_reports_deleted_files(backup_dir):
    _dump(backup_dir, "20200101-030000")
    summary = bm.purge_expired_database_backups(now=NOW)
    assert summary.deleted_files == ["isgsuite-20200101-030000.dump"]
    assert summary.kept == 0


def test_purge_missing_directory_is_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "yok"))
    summary = bm.purge_expired_database_backups(now=NOW)
    assert (summary.kept, summary.deleted, summary.failed) == (0, 0, 0)


def test_purge_uses_directory_override(tmp_path):
    root = tmp_path / "custom"
    root.mkdir()
    ancient = _dump(root, "20200101-030000")
    bm.purge_expired_database_backups(now=NOW, directory=root)
    assert ancient.exists() is False


def test_purge_counts_failures(backup_dir, monkeypatch):
    ancient = _dump(backup_dir, "20200101-030000")

    def _boom(self, *args, **kwargs):
        raise OSError("locked")

    monkeypatch.setattr(Path, "unlink", _boom)
    summary = bm.purge_expired_database_backups(now=NOW)
    assert summary.failed == 1
    assert summary.deleted == 0
    assert ancient.exists() is True


def test_purge_deletes_offsite_copy_too(backup_dir, monkeypatch):
    monkeypatch.setattr(settings, "backup_remote_enabled", True)
    remote = _FakeRemote()
    monkeypatch.setattr(bm, "offsite_store", lambda: remote)
    ancient = _dump(backup_dir, "20200101-030000")
    remote.objects["db-backups/" + ancient.name] = ancient.read_bytes()
    bm.purge_expired_database_backups(now=NOW)
    assert "db-backups/isgsuite-20200101-030000.dump" in remote.deleted


def test_retention_summary_shape(backup_dir):
    summary = bm.purge_expired_database_backups(now=NOW)
    assert set(summary.__dataclass_fields__) == {"kept", "deleted", "failed", "deleted_files"}


def test_weekly_window_respects_config(backup_dir, monkeypatch):
    monkeypatch.setattr(settings, "db_backup_weekly_retention_weeks", 1)
    older = _dump(backup_dir, "20260727-030000")
    newer = _dump(backup_dir, "20260729-030000")
    bm.purge_expired_database_backups(now=NOW)
    # Haftalık pencere 1 haftaya indiği için Temmuz yedekleri aylık katmana düşer:
    # ayın en yenisi korunur, diğeri silinir.
    assert newer.exists() is True
    assert older.exists() is False


def test_monthly_window_respects_config(backup_dir, monkeypatch):
    monkeypatch.setattr(settings, "db_backup_monthly_retention_months", 1)
    old = _dump(backup_dir, "20260320-030000")
    bm.purge_expired_database_backups(now=NOW)
    assert old.exists() is False


# --- Offsite kopya ---------------------------------------------------------


def test_offsite_upload_verifies_checksum(tmp_path):
    source = tmp_path / "isgsuite-20260921-030000.dump"
    source.write_bytes(b"payload")
    result = bm.upload_backup_to_offsite(source, store=_FakeRemote())
    assert result["uploaded"] is True
    assert result["key"] == "db-backups/isgsuite-20260921-030000.dump"
    assert result["checksum"] == hashlib.sha256(b"payload").hexdigest()
    assert result["size_bytes"] == 7


def test_offsite_upload_deletes_corrupt_object(tmp_path):
    source = tmp_path / "isgsuite-20260921-030000.dump"
    source.write_bytes(b"payload")
    remote = _FakeRemote(corrupt=True)
    with pytest.raises(bm.BackupOffsiteError):
        bm.upload_backup_to_offsite(source, store=remote)
    assert remote.objects == {}
    assert source.exists() is True


def test_offsite_upload_missing_file_raises(tmp_path):
    with pytest.raises(bm.BackupOffsiteError):
        bm.upload_backup_to_offsite(tmp_path / "yok.dump", store=_FakeRemote())


def test_offsite_upload_uses_provided_key(tmp_path):
    source = tmp_path / "isgsuite-20260921-030000.dump"
    source.write_bytes(b"payload")
    remote = _FakeRemote()
    result = bm.upload_backup_to_offsite(source, key="custom/key.dump", store=remote)
    assert result["key"] == "custom/key.dump"
    assert "custom/key.dump" in remote.objects


def test_offsite_key_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_remote_prefix", "../evil")
    with pytest.raises(bm.BackupOffsiteError):
        bm.offsite_key(tmp_path / "x.dump")


def test_offsite_key_default_prefix(tmp_path):
    assert bm.offsite_key(tmp_path / "x.dump") == "db-backups/x.dump"


def test_offsite_disabled_returns_reason(tmp_path):
    source = tmp_path / "isgsuite-20260921-030000.dump"
    source.write_bytes(b"x")
    assert bm.upload_backup_to_offsite(source) == {"uploaded": False, "reason": "remote-disabled"}


def test_offsite_store_none_when_disabled():
    assert bm.offsite_store() is None


def test_offsite_upload_requires_range_support(tmp_path):
    class _NoRange:
        def put_file(self, key, path, *, content_type=None):
            return key

        def remote_size(self, key):
            return 7

    source = tmp_path / "isgsuite-20260921-030000.dump"
    source.write_bytes(b"payload")
    with pytest.raises(bm.BackupOffsiteError):
        bm.upload_backup_to_offsite(source, store=_NoRange())


# --- RPO izleme ------------------------------------------------------------


def test_status_reports_age_and_health(backup_dir):
    _dump(backup_dir, "20260921-030000")
    status = bm.database_backup_status(now=datetime(2026, 9, 21, 12, 0, 0))
    assert status["backup_count"] == 1
    assert status["age_hours"] == pytest.approx(9.0)
    assert status["healthy"] is True
    assert status["max_age_hours"] == 36


def test_status_unhealthy_when_stale(backup_dir):
    _dump(backup_dir, "20260918-030000")
    status = bm.database_backup_status(now=datetime(2026, 9, 21, 12, 0, 0))
    assert status["healthy"] is False
    assert status["age_hours"] > status["max_age_hours"]


def test_status_without_backups(backup_dir):
    status = bm.database_backup_status(now=NOW)
    assert status["latest_backup_at"] is None
    assert status["age_hours"] is None
    assert status["healthy"] is False


def test_status_counts_encrypted_and_plain(backup_dir):
    _dump(backup_dir, "20260921-030000")
    _dump(backup_dir, "20260920-030000", suffix=".db.enc")
    status = bm.database_backup_status(now=datetime(2026, 9, 21, 12, 0, 0))
    assert status["backup_count"] == 2


def test_status_picks_newest(backup_dir):
    _dump(backup_dir, "20260901-030000")
    _dump(backup_dir, "20260920-030000")
    status = bm.database_backup_status(now=NOW)
    assert status["latest_backup_at"].startswith("2026-09-20")


def test_status_reports_offsite_flags(backup_dir, monkeypatch):
    monkeypatch.setattr(settings, "backup_remote_enabled", True)
    monkeypatch.setattr(settings, "backup_remote_required", True)
    status = bm.database_backup_status(now=NOW)
    assert status["offsite_enabled"] is True
    assert status["offsite_required"] is True


def test_status_respects_enabled_flag(backup_dir, monkeypatch):
    monkeypatch.setattr(settings, "db_backup_enabled", False)
    assert bm.database_backup_status(now=NOW)["enabled"] is False


def test_status_max_age_boundary_is_healthy(backup_dir):
    _dump(backup_dir, "20260920-000000")
    status = bm.database_backup_status(now=datetime(2026, 9, 21, 12, 0, 0))
    assert status["age_hours"] == pytest.approx(36.0)
    assert status["healthy"] is True
