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
    return zpath


def test_inspect_backup_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", False)
    zpath = _make_zip(tmp_path)
    plan = br.inspect_backup_file(zpath)
    assert plan.format_version == 2
    assert plan.osgb_name == "Test OSGB"
    assert plan.companies[0]["id"] == 9
    assert "files/9/doc.pdf" in plan.file_entries
    assert plan.restore_enabled is False


def test_restore_blocked_when_flag_off(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", False)
    zpath = _make_zip(tmp_path)
    with pytest.raises(HTTPException) as exc:
        br.restore_files_from_backup(zpath, dry_run=True)
    assert exc.value.status_code == 403


def test_restore_dry_run_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", True)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    zpath = _make_zip(tmp_path)
    result = br.restore_files_from_backup(zpath, dry_run=True)
    assert result["dry_run"] is True
    assert result["files_touched"] == 1
    assert not (tmp_path / "uploads" / "9" / "doc.pdf").exists()


def test_restore_writes_with_confirm(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", True)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    zpath = _make_zip(tmp_path)
    result = br.restore_files_from_backup(zpath, dry_run=False, confirm="RESTORE")
    assert result["dry_run"] is False
    assert (tmp_path / "uploads" / "9" / "doc.pdf").read_bytes().startswith(b"%PDF")
