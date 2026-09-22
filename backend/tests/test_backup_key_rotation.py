"""Yedek anahtar rotasyonu ve bütünlük taraması."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from scripts import backup_key_rotation as bkr

OLD_KEY = "old-backup-key-at-least-32-characters!!"
NEW_KEY = "new-backup-key-at-least-32-characters!!"


@pytest.fixture()
def backup_root(tmp_path, monkeypatch):
    root = tmp_path / "backups"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "backup_dir", str(root))
    return root


def _encrypted(root: Path, name: str, payload: bytes, key: str = OLD_KEY) -> Path:
    path = root / name
    path.write_bytes(bkr._fernet(key).encrypt(payload))
    return path


def test_rotate_reencrypts_and_new_key_opens(backup_root):
    path = _encrypted(backup_root, "isgsuite-20260921-030000.dump.enc", b"payload")

    result = bkr.rotate_backup_key(old_key=OLD_KEY, new_key=NEW_KEY)

    assert result["status"] == "ok"
    assert result["count"] == 1
    assert bkr._fernet(NEW_KEY).decrypt(path.read_bytes()) == b"payload"
    with pytest.raises(Exception):
        bkr._fernet(OLD_KEY).decrypt(path.read_bytes())


def test_rotate_dry_run_does_not_modify(backup_root):
    path = _encrypted(backup_root, "isgsuite-20260921-030000.dump.enc", b"payload")
    before = path.read_bytes()

    result = bkr.rotate_backup_key(old_key=OLD_KEY, new_key=NEW_KEY, dry_run=True)

    assert result["dry_run"] is True
    assert result["count"] == 1
    assert path.read_bytes() == before


def test_rotate_aborts_when_old_key_wrong(backup_root):
    path = _encrypted(backup_root, "isgsuite-20260921-030000.dump.enc", b"payload")
    before = path.read_bytes()

    result = bkr.rotate_backup_key(old_key="wrong-key-at-least-32-characters-long!", new_key=NEW_KEY)

    assert result["status"] == "aborted"
    assert result["rotated"] == []
    assert path.read_bytes() == before


def test_rotate_handles_multiple_files(backup_root):
    _encrypted(backup_root, "isgsuite-20260920-030000.dump.enc", b"a")
    _encrypted(backup_root, "isgsuite-20260921-030000.dump.enc", b"b")

    result = bkr.rotate_backup_key(old_key=OLD_KEY, new_key=NEW_KEY)

    assert result["count"] == 2


def test_rotate_with_no_files_is_ok(backup_root):
    result = bkr.rotate_backup_key(old_key=OLD_KEY, new_key=NEW_KEY)
    assert result["status"] == "ok"
    assert result["count"] == 0


def test_rotate_leaves_no_pre_rotation_files(backup_root):
    _encrypted(backup_root, "isgsuite-20260921-030000.dump.enc", b"payload")
    bkr.rotate_backup_key(old_key=OLD_KEY, new_key=NEW_KEY)
    assert list(backup_root.glob("*.pre-rotation")) == []


def test_verify_reports_clean_backups(backup_root):
    (backup_root / "isgsuite-20260921-030000.dump").write_bytes(b"dump")
    result = bkr.verify_all_backups()
    assert result["status"] == "ok"
    assert result["checked"] == 1
    assert result["corrupt"] == []


def test_verify_detects_empty_backup(backup_root):
    (backup_root / "isgsuite-20260921-030000.dump").write_bytes(b"")
    result = bkr.verify_all_backups()
    assert result["status"] == "degraded"
    assert result["corrupt"]


def test_verify_missing_directory_is_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "yok"))
    result = bkr.verify_all_backups()
    assert result["status"] == "ok"
    assert result["checked"] == 0


def test_verify_ignores_unrelated_files(backup_root):
    (backup_root / "notes.txt").write_text("x", encoding="utf-8")
    result = bkr.verify_all_backups()
    assert result["checked"] == 0


def test_notify_skips_when_clean(backup_root):
    result = bkr.verify_all_backups()
    assert bkr._notify_backup_integrity(result) == 0


def test_main_requires_keys_for_rotate(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["backup_key_rotation", "--rotate"])
    assert bkr.main() == 2
    assert "zorunludur" in capsys.readouterr().out


def test_main_verify_exit_zero_when_clean(backup_root, monkeypatch, capsys):
    (backup_root / "isgsuite-20260921-030000.dump").write_bytes(b"dump")
    monkeypatch.setattr("sys.argv", ["backup_key_rotation", "--no-notify"])
    assert bkr.main() == 0
    assert '"status": "ok"' in capsys.readouterr().out


def test_main_verify_exit_one_when_corrupt(backup_root, monkeypatch, capsys):
    (backup_root / "isgsuite-20260921-030000.dump").write_bytes(b"")
    monkeypatch.setattr("sys.argv", ["backup_key_rotation", "--no-notify"])
    assert bkr.main() == 1
