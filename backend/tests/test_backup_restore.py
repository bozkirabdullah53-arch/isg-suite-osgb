"""Backup restore plan — yazmadan inceleme + gated restore."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.services import backup_restore as br


def _make_zip(tmp: Path) -> Path:
    zpath = tmp / "backup-test.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format_version": 2,
                    "created_at": "2026-07-24T00:00:00Z",
                    "osgb_id": 1,
                    "osgb_name": "Test OSGB",
                    "companies": [{"id": 9, "name": "Firma A"}],
                },
                ensure_ascii=False,
            ),
        )
        zf.writestr("documents.json", "[]")
        zf.writestr("employees.json", "[]")
        zf.writestr("files/9/doc.pdf", b"%PDF-1.4")
        zf.writestr("osgb_files/visits/n.pdf", b"%PDF-osgb")
    return zpath


def test_inspect_backup_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", False)
    zpath = _make_zip(tmp_path)
    plan = br.inspect_backup_file(zpath)
    assert plan.format_version == 2
    assert plan.osgb_name == "Test OSGB"
    assert plan.companies[0]["id"] == 9
    assert "files/9/doc.pdf" in plan.file_entries
    assert "osgb_files/visits/n.pdf" in plan.file_entries
    assert plan.restore_enabled is False
    assert any("osgb_files" in n for n in plan.notes)


def test_restore_dry_run_allowed_when_flag_off(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", False)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    zpath = _make_zip(tmp_path)
    result = br.restore_files_from_backup(zpath, dry_run=True)
    assert result["dry_run"] is True
    assert result["files_touched"] == 2
    assert "1/visits/n.pdf" in result["sample"]
    assert not (tmp_path / "uploads" / "9" / "doc.pdf").exists()


def test_restore_write_blocked_when_flag_off(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", False)
    zpath = _make_zip(tmp_path)
    with pytest.raises(HTTPException) as exc:
        br.restore_files_from_backup(zpath, dry_run=False, confirm="RESTORE")
    assert exc.value.status_code == 403


def test_restore_dry_run_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", True)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    zpath = _make_zip(tmp_path)
    result = br.restore_files_from_backup(zpath, dry_run=True)
    assert result["dry_run"] is True
    assert result["files_touched"] == 2
    assert "9/doc.pdf" in result["sample"]
    assert "1/visits/n.pdf" in result["sample"]
    assert not (tmp_path / "uploads" / "9" / "doc.pdf").exists()


def test_restore_writes_with_confirm(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", True)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    zpath = _make_zip(tmp_path)
    result = br.restore_files_from_backup(zpath, dry_run=False, confirm="RESTORE")
    assert result["dry_run"] is False
    assert (tmp_path / "uploads" / "9" / "doc.pdf").read_bytes().startswith(b"%PDF")
    assert (tmp_path / "uploads" / "1" / "visits" / "n.pdf").read_bytes() == b"%PDF-osgb"


def test_restore_skips_osgb_files_without_osgb_id(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", True)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    zpath = tmp_path / "no-osgb.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"format_version": 2, "osgb_name": "X"}))
        zf.writestr("osgb_files/visits/x.pdf", b"%PDF")
    result = br.restore_files_from_backup(zpath, dry_run=True)
    assert result["files_touched"] == 0
    assert "osgb_files/visits/x.pdf" in result["skipped"]


def test_backup_encryption_readiness_missing(monkeypatch):
    monkeypatch.setattr(settings, "backup_encryption_key", None)
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    monkeypatch.setattr(settings, "backup_restore_enabled", False)
    assert br.backup_encryption_key_status() == "missing"
    assert br.backup_crypto_ready_label() == "not_ready"
    assert br.backup_encryption_readiness()["can_encrypt"] is False


def test_backup_encryption_readiness_weak(monkeypatch):
    monkeypatch.setattr(settings, "backup_encryption_key", "change-me-in-production-at-least-32-characters!")
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    assert br.backup_encryption_key_status() == "weak"
    assert br.backup_crypto_ready_label() == "not_ready"


def test_backup_encryption_readiness_dedicated(monkeypatch):
    monkeypatch.setattr(settings, "backup_encryption_key", "dedicated-backup-key-at-least-32chars!!")
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    assert br.backup_encryption_key_status() == "dedicated"
    assert br.backup_crypto_ready_label() == "ok"
    assert br.backup_encryption_readiness()["can_encrypt"] is True


def test_enable_backup_crypto_production_secret_fallback(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "backup_encryption_key", None)
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    monkeypatch.setattr(settings, "backup_encryption_force_off", False)
    monkeypatch.setattr(settings, "secret_key", "prod-secret-key-at-least-32-characters-long!!")
    assert br.enable_backup_crypto_for_production().startswith("enabled:")
    assert br.backup_encryption_key_status() == "secret_key_fallback"
    assert br.backup_crypto_ready_label() == "ok"
    assert br.backup_encryption_key_material() == settings.secret_key


def test_enable_backup_crypto_force_off(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "backup_encryption_key", None)
    monkeypatch.setattr(settings, "backup_encryption_force_off", True)
    monkeypatch.setattr(settings, "secret_key", "prod-secret-key-at-least-32-characters-long!!")
    assert br.enable_backup_crypto_for_production() == "force-off"
    assert br.backup_encryption_key_material() == ""


def test_backup_decrypt_falls_back_to_secret_after_dedicated(tmp_path, monkeypatch):
    import base64
    import hashlib
    import zipfile

    from cryptography.fernet import Fernet

    secret = "old-backup-secret-at-least-32-characters!"
    dedicated = "new-dedicated-backup-key-32chars-min!!"
    monkeypatch.setattr(settings, "secret_key", secret)
    monkeypatch.setattr(settings, "backup_encryption_key", None)
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", True)
    zpath = _make_zip(tmp_path)
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    enc = tmp_path / "legacy.zip.enc"
    enc.write_bytes(Fernet(base64.urlsafe_b64encode(digest)).encrypt(zpath.read_bytes()))
    monkeypatch.setattr(settings, "backup_encryption_key", dedicated)
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    plan = br.inspect_backup_file(enc)
    assert plan.encrypted is True
    assert plan.document_count >= 0


def test_restore_write_still_blocked_when_crypto_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", False)
    monkeypatch.setattr(settings, "backup_encryption_key", "dedicated-backup-key-at-least-32chars!!")
    zpath = _make_zip(tmp_path)
    dry = br.restore_files_from_backup(zpath, dry_run=True)
    assert dry["files_touched"] == 2
    with pytest.raises(HTTPException) as exc:
        br.restore_files_from_backup(zpath, dry_run=False, confirm="RESTORE")
    assert exc.value.status_code == 403
