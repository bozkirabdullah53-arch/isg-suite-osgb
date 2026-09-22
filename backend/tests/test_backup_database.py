"""Zamanlanmış veritabanı yedeği — sertleştirme ve fail-closed davranış."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.core.config import settings
from scripts import backup_database as bd


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr(settings, "backup_remote_enabled", False)
    monkeypatch.setattr(settings, "backup_remote_required", False)
    monkeypatch.setattr(settings, "backup_encryption_key", "")
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    monkeypatch.setattr(settings, "backup_encryption_force_off", False)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "db_backup_enabled", True)
    return tmp_path


def test_sqlite_backup_copies_file(isolated, monkeypatch):
    source = isolated / "source.db"
    source.write_bytes(b"sqlite-bytes")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")
    produced = bd.backup_sqlite(settings.database_url, isolated / "out")
    assert produced.read_bytes() == b"sqlite-bytes"


def test_sqlite_backup_missing_file_raises(isolated, monkeypatch):
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{isolated / 'yok.db'}")
    with pytest.raises(bd.BackupError):
        bd.backup_sqlite(settings.database_url, isolated / "out")


def test_postgres_backup_requires_pg_dump(isolated, monkeypatch):
    monkeypatch.setattr(bd.shutil, "which", lambda name: None)
    with pytest.raises(bd.BackupError, match="pg_dump"):
        bd.backup_postgresql("postgresql://u:p@localhost/db", isolated / "out")


def test_postgres_password_not_in_argv(isolated, monkeypatch):
    captured: dict = {}

    def _fake_run(command, check, env, capture_output, text):
        captured["command"] = command
        captured["env"] = env
        Path(command[command.index("--file") + 1]).write_bytes(b"dump")

        class _Done:
            returncode = 0

        return _Done()

    monkeypatch.setattr(bd.shutil, "which", lambda name: "/usr/bin/pg_dump")
    monkeypatch.setattr(bd.subprocess, "run", _fake_run)
    bd.backup_postgresql("postgresql://user:supersecret@localhost:5432/isg", isolated / "out")

    assert "supersecret" not in " ".join(captured["command"])
    assert captured["env"]["PGPASSWORD"] == "supersecret"


def test_production_requires_encryption_key(isolated, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", "change-me")
    with pytest.raises(bd.BackupError, match="şifreleme"):
        bd._resolve_encryption()


def test_production_rejects_weak_fallback(isolated, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", "change-me")
    monkeypatch.setattr(settings, "backup_encryption_key", "short")
    with pytest.raises(bd.BackupError):
        bd._resolve_encryption()


def test_production_accepts_strong_secret_fallback(isolated, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", "prod-secret-key-at-least-32-characters-long!!")
    encrypt, status = bd._resolve_encryption()
    assert encrypt is True
    assert status == "secret_key_fallback"


def test_non_production_allows_unencrypted(isolated, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    encrypt, status = bd._resolve_encryption()
    assert encrypt is False
    assert status == "missing"


def test_run_backup_sqlite_roundtrip(isolated, monkeypatch):
    source = isolated / "source.db"
    source.write_bytes(b"sqlite-bytes")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")

    result = bd.run_backup()

    assert result["status"] == "ok"
    assert result["encrypted"] is False
    assert result["file"].startswith("isgsuite-")
    assert result["file"].endswith(".db")
    assert Path(result["path"]).read_bytes() == b"sqlite-bytes"
    assert result["offsite"]["uploaded"] is False
    assert "retention" in result


def test_run_backup_encrypts_when_key_present(isolated, monkeypatch):
    source = isolated / "source.db"
    source.write_bytes(b"sqlite-bytes")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")
    monkeypatch.setattr(settings, "backup_encryption_key", "dedicated-backup-key-at-least-32chars!!")

    result = bd.run_backup()

    assert result["encrypted"] is True
    assert result["file"].endswith(".db.enc")
    assert result["encryption_key_status"] == "dedicated"


def test_main_prints_json_and_exit_zero(isolated, monkeypatch, capsys):
    source = isolated / "source.db"
    source.write_bytes(b"x")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")

    code = bd.main()
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert code == 0
    assert payload["status"] == "ok"


def test_main_returns_error_json(isolated, monkeypatch, capsys):
    monkeypatch.setattr(settings, "database_url", "mysql://unsupported")

    code = bd.main()
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert code == 1
    assert payload["status"] == "error"
    assert payload["error_class"] == "BackupError"


def test_run_backup_fails_when_offsite_required_but_unavailable(isolated, monkeypatch):
    source = isolated / "source.db"
    source.write_bytes(b"x")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")
    monkeypatch.setattr(settings, "backup_remote_required", True)

    with pytest.raises(bd.BackupError, match="Offsite"):
        bd.run_backup()


def test_run_backup_applies_retention(isolated, monkeypatch):
    source = isolated / "source.db"
    source.write_bytes(b"x")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    ancient = backup_dir / "isgsuite-20200101-030000.db"
    ancient.write_bytes(b"old")

    result = bd.run_backup()

    assert ancient.exists() is False
    assert "isgsuite-20200101-030000.db" in result["retention"]["deleted_files"]


def test_safe_pg_url_strips_password():
    safe, password = bd._safe_pg_url("postgresql+psycopg://user:p%40ss@host:5432/db?sslmode=require")
    assert password == "p@ss"
    assert "p%40ss" not in safe
    assert "sslmode=require" in safe


def test_backup_error_is_runtime_error():
    assert issubclass(bd.BackupError, RuntimeError)


def test_encrypt_backup_removes_plain_file(isolated, monkeypatch):
    monkeypatch.setattr(settings, "backup_encryption_key", "dedicated-backup-key-at-least-32chars!!")
    plain = isolated / "isgsuite-20260921-030000.db"
    plain.write_bytes(b"plain-bytes")

    encrypted = bd._encrypt_backup(plain)

    assert encrypted.name.endswith(".db.enc")
    assert encrypted.exists() is True
    assert plain.exists() is False


def test_encrypt_backup_without_key_raises(isolated):
    plain = isolated / "isgsuite-20260921-030000.db"
    plain.write_bytes(b"plain-bytes")
    with pytest.raises(bd.BackupError):
        bd._encrypt_backup(plain)


def test_is_production_detects_aliases(isolated, monkeypatch):
    for env in ("production", "PROD", "live"):
        monkeypatch.setattr(settings, "environment", env)
        assert bd._is_production() is True
    monkeypatch.setattr(settings, "environment", "development")
    assert bd._is_production() is False


def test_run_backup_unsupported_database(isolated, monkeypatch):
    monkeypatch.setattr(settings, "database_url", "mysql://x")
    with pytest.raises(bd.BackupError, match="Desteklenmeyen"):
        bd.run_backup()


def test_postgres_backup_empty_output_raises(isolated, monkeypatch):
    def _fake_run(command, check, env, capture_output, text):
        Path(command[command.index("--file") + 1]).write_bytes(b"")

        class _Done:
            returncode = 0

        return _Done()

    monkeypatch.setattr(bd.shutil, "which", lambda name: "/usr/bin/pg_dump")
    monkeypatch.setattr(bd.subprocess, "run", _fake_run)
    with pytest.raises(bd.BackupError, match="boş"):
        bd.backup_postgresql("postgresql://user:pw@localhost:5432/isg", isolated / "out")


def test_postgres_backup_failure_message(isolated, monkeypatch):
    import subprocess

    def _fake_run(command, check, env, capture_output, text):
        raise subprocess.CalledProcessError(1, command, stderr="connection refused")

    monkeypatch.setattr(bd.shutil, "which", lambda name: "/usr/bin/pg_dump")
    monkeypatch.setattr(bd.subprocess, "run", _fake_run)
    with pytest.raises(bd.BackupError, match="connection refused"):
        bd.backup_postgresql("postgresql://user:pw@localhost:5432/isg", isolated / "out")


def test_backup_dir_is_created(isolated, monkeypatch):
    source = isolated / "source.db"
    source.write_bytes(b"x")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")
    monkeypatch.setattr(settings, "backup_dir", str(isolated / "nested" / "backups"))
    bd.run_backup()
    assert (isolated / "nested" / "backups").is_dir()


def test_run_backup_retention_keeps_recent(isolated, monkeypatch):
    source = isolated / "source.db"
    source.write_bytes(b"x")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    recent = backup_dir / f"isgsuite-{stamp}.db"
    recent.write_bytes(b"recent")

    result = bd.run_backup()

    assert recent.exists() is True
    assert result["retention"]["deleted"] == 0
