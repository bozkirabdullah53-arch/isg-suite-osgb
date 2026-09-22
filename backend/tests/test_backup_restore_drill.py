"""Gerçek yedek üzerinde geri yükleme tatbikatı (İBYS Yedekleme Prosedürü §7)."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from app.core.config import settings
from scripts import backup_restore_drill as drill


@pytest.fixture()
def backup_root(tmp_path, monkeypatch):
    root = tmp_path / "backups"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "backup_dir", str(root))
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "backup_restore_enabled", False)
    monkeypatch.setattr(settings, "backup_encryption_key", "")
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    return root


def _tenant_zip(root: Path, *, name: str = "backup-v3.zip", files: int = 2) -> Path:
    path = root / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format_version": 3,
                    "created_at": "2026-09-20T00:00:00Z",
                    "osgb_id": 1,
                    "osgb_name": "Drill OSGB",
                    "companies": [{"id": 9, "name": "Firma A"}],
                    "domain_counts": {"health_records": 1},
                },
                ensure_ascii=False,
            ),
        )
        zf.writestr("health_records.json", json.dumps([{"id": 1, "company_id": 9}]))
        for index in range(files):
            zf.writestr(f"files/9/doc{index}.pdf", b"%PDF-1.4")
    return path


def test_drill_passes_on_real_archive(backup_root):
    path = _tenant_zip(backup_root)
    evidence = drill.run_drill(archive=path)
    assert evidence["result"] == "pass"
    assert evidence["kind"] == "archive"
    assert evidence["archive"]["name"] == "backup-v3.zip"
    assert evidence["checks"]["files_touched"] == 2
    assert evidence["checks"]["domain_counts"]["health_records"] == 1
    assert evidence["mode"] == "real_archive"


def test_drill_fails_when_no_backup_exists(backup_root):
    evidence = drill.run_drill()
    assert evidence["result"] == "fail"
    assert "bulunamadı" in evidence["failure_reason"]


def test_drill_picks_latest_archive(backup_root):
    old = _tenant_zip(backup_root, name="backup-old.zip")
    new = _tenant_zip(backup_root, name="backup-new.zip")
    import os
    import time

    past = time.time() - 3600
    os.utime(old, (past, past))
    evidence = drill.run_drill(latest=True)
    assert evidence["archive"]["name"] == new.name


def test_drill_handles_database_dump(backup_root):
    dump = backup_root / "isgsuite-20260921-030000.dump"
    dump.write_bytes(b"pgdump-bytes")
    evidence = drill.run_drill(archive=dump)
    assert evidence["result"] == "pass"
    assert evidence["kind"] == "database_dump"
    assert evidence["checks"]["size_bytes"] == len(b"pgdump-bytes")
    assert len(evidence["checks"]["sha256"]) == 64


def test_drill_fails_on_empty_dump(backup_root):
    dump = backup_root / "isgsuite-20260921-030000.dump"
    dump.write_bytes(b"")
    evidence = drill.run_drill(archive=dump)
    assert evidence["result"] == "fail"


def test_drill_fails_on_corrupt_archive(backup_root):
    broken = backup_root / "broken.zip"
    broken.write_bytes(b"not-a-zip")
    evidence = drill.run_drill(archive=broken)
    assert evidence["result"] == "fail"
    assert evidence["failure_reason"]


def test_drill_writes_evidence_file(backup_root, tmp_path):
    path = _tenant_zip(backup_root)
    out = tmp_path / "logs" / "backup-restore-drill.json"
    drill.run_drill(archive=path, out=out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["result"] == "pass"
    assert "ran_at" in payload


def test_drill_writes_evidence_on_failure(backup_root, tmp_path):
    out = tmp_path / "logs" / "drill.json"
    drill.run_drill(out=out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["result"] == "fail"


def test_drill_never_writes_restored_files(backup_root, tmp_path):
    path = _tenant_zip(backup_root)
    drill.run_drill(archive=path)
    assert not (tmp_path / "uploads" / "9" / "doc0.pdf").exists()


def test_drill_records_restore_write_flag(backup_root, monkeypatch):
    monkeypatch.setattr(settings, "backup_restore_enabled", True)
    path = _tenant_zip(backup_root)
    evidence = drill.run_drill(archive=path)
    assert evidence["restore_writes_enabled"] is True


def test_find_latest_backup_returns_none_when_empty(backup_root):
    assert drill.find_latest_backup() is None


def test_main_returns_nonzero_on_failure(backup_root, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["drill"])
    assert drill.main() == 1
    assert json.loads(capsys.readouterr().out)["result"] == "fail"


def test_main_returns_zero_on_success(backup_root, monkeypatch, capsys):
    path = _tenant_zip(backup_root)
    monkeypatch.setattr("sys.argv", ["drill", "--archive", str(path)])
    assert drill.main() == 0
    assert json.loads(capsys.readouterr().out)["result"] == "pass"


def test_drill_detects_manifest_mismatch(backup_root, monkeypatch):
    """dry-run dosya sayısı manifest ile uyuşmazsa tatbikat FAIL olmalı."""
    path = _tenant_zip(backup_root)
    monkeypatch.setattr(
        drill.br,
        "restore_files_from_backup",
        lambda *a, **k: {"dry_run": True, "files_touched": 0, "skipped": []},
    )
    evidence = drill.run_drill(archive=path)
    assert evidence["result"] == "fail"
    assert "uyuşmuyor" in evidence["failure_reason"]


def test_drill_reports_encrypted_archive(backup_root, monkeypatch):
    path = _tenant_zip(backup_root, name="backup-enc.zip")
    monkeypatch.setattr(drill.br, "inspect_backup_file", lambda p, **k: type("P", (), {
        "format_version": 4, "encrypted": True, "domain_counts": {}, "file_entries": [],
        "document_count": 0, "employee_count": 0, "osgb_id": 1, "osgb_name": "X",
    })())
    monkeypatch.setattr(
        drill.br, "restore_files_from_backup", lambda *a, **k: {"files_touched": 0, "skipped": []}
    )
    evidence = drill.run_drill(archive=path)
    assert evidence["checks"]["encrypted"] is True
    assert evidence["result"] == "pass"


def test_drill_unknown_extension_fails(backup_root):
    other = backup_root / "weird.bin"
    other.write_bytes(b"x")
    evidence = drill.run_drill(archive=other)
    assert evidence["result"] == "fail"
    assert evidence["kind"] == "unknown"
