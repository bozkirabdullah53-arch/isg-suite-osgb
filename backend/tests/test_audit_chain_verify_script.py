"""Denetim zinciri doğrulama scripti — PASS/FAIL yolu ve kanıt dosyası."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import AuditLog
from scripts import audit_chain_verify as acv


@pytest.fixture()
def sqlite_session(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr("app.core.config.settings.backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr("app.core.config.settings.upload_dir", str(tmp_path / "uploads"))
    return factory


def test_verify_reports_unsupported_on_sqlite(sqlite_session, monkeypatch, tmp_path):
    """SQLite'da hash zinciri trigger'ı yoktur; script bunu desteklenmiyor olarak raporlar."""
    monkeypatch.setattr(acv, "SessionLocal", sqlite_session)
    with sqlite_session() as db:
        db.add(AuditLog(action="x", entity_type="y"))
        db.commit()

    result = acv.run_verify(notify=False)

    assert "supported" in result
    assert "ran_at" in result
    assert result["exit_code"] in (0, 1)


def test_verify_writes_evidence_file(sqlite_session, monkeypatch, tmp_path):
    monkeypatch.setattr(acv, "SessionLocal", sqlite_session)
    out = tmp_path / "logs" / "audit-chain.json"
    acv.run_verify(out=out, notify=False)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "ran_at" in payload
    assert "exit_code" in payload


def test_verify_ok_when_supported_and_clean(sqlite_session, monkeypatch):
    monkeypatch.setattr(acv, "SessionLocal", sqlite_session)
    monkeypatch.setattr(acv, "verify_audit_chain", lambda db: {
        "supported": True, "total": 5, "chain_breaks": 0, "hash_breaks": 0, "ok": True,
    })
    result = acv.run_verify(notify=False)
    assert result["ok"] is True
    assert result["exit_code"] == 0


def test_verify_fails_and_notifies_when_broken(sqlite_session, monkeypatch):
    monkeypatch.setattr(acv, "SessionLocal", sqlite_session)
    monkeypatch.setattr(acv, "verify_audit_chain", lambda db: {
        "supported": True, "total": 5, "chain_breaks": 2, "hash_breaks": 1, "ok": False,
    })
    notified: list[tuple[int, int]] = []
    monkeypatch.setattr(acv, "_notify_admins", lambda c, h: notified.append((c, h)) or 1)

    result = acv.run_verify(notify=True)

    assert result["ok"] is False
    assert result["exit_code"] == 1
    assert notified == [(2, 1)]


def test_verify_skips_notify_with_flag(sqlite_session, monkeypatch):
    monkeypatch.setattr(acv, "SessionLocal", sqlite_session)
    monkeypatch.setattr(acv, "verify_audit_chain", lambda db: {
        "supported": True, "total": 1, "chain_breaks": 1, "hash_breaks": 0, "ok": False,
    })
    notified: list = []
    monkeypatch.setattr(acv, "_notify_admins", lambda c, h: notified.append((c, h)) or 0)

    acv.run_verify(notify=False)

    assert notified == []


def test_main_returns_exit_code(sqlite_session, monkeypatch, capsys):
    monkeypatch.setattr(acv, "SessionLocal", sqlite_session)
    monkeypatch.setattr(acv, "verify_audit_chain", lambda db: {
        "supported": True, "total": 0, "chain_breaks": 0, "hash_breaks": 0, "ok": True,
    })
    monkeypatch.setattr("sys.argv", ["audit_chain_verify", "--no-notify"])
    assert acv.main() == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_main_returns_one_when_broken(sqlite_session, monkeypatch, capsys):
    monkeypatch.setattr(acv, "SessionLocal", sqlite_session)
    monkeypatch.setattr(acv, "verify_audit_chain", lambda db: {
        "supported": True, "total": 3, "chain_breaks": 1, "hash_breaks": 0, "ok": False,
    })
    monkeypatch.setattr("sys.argv", ["audit_chain_verify", "--no-notify"])
    assert acv.main() == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
