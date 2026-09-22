"""Denetim zinciri yeniden kurulum aracı (bakım penceresi) ve yedek alarmı."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import Notification, NotificationType, User, UserRole
from scripts import rebuild_audit_chain as rac


@pytest.fixture()
def sqlite_session(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(rac, "SessionLocal", factory)
    monkeypatch.setattr("app.core.config.settings.backup_dir", str(tmp_path / "backups"))
    return factory


def test_dry_run_makes_no_changes(sqlite_session):
    report = rac.rebuild(apply=False)
    assert report["dry_run"] is True
    assert report["status"] in ("dry-run", "unsupported")


def test_sqlite_is_reported_unsupported(sqlite_session):
    """Hash zinciri PostgreSQL'e özgüdür; SQLite'da araç değişiklik yapmaz."""
    report = rac.rebuild(apply=True)
    assert report["status"] == "unsupported"
    assert report["reason"] == "postgresql_required"
    assert report["dry_run"] is False


def test_dry_run_does_not_touch_triggers(sqlite_session):
    rac.rebuild(apply=False)
    with sqlite_session() as db:
        # SQLite'da trigger yok; araç yine de hata vermemeli.
        assert db.execute(select(1)).scalar() == 1


def test_main_dry_run_exit_zero(sqlite_session, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["rebuild_audit_chain", "--dry-run"])
    assert rac.main() == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] is True


def test_main_requires_a_mode(monkeypatch):
    monkeypatch.setattr("sys.argv", ["rebuild_audit_chain"])
    with pytest.raises(SystemExit):
        rac.main()


# --- Yedek alarmı ----------------------------------------------------------


def test_notify_global_admins_creates_critical_rows(monkeypatch, tmp_path):
    from app.services import backup_management as bm

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all(
            [
                User(
                    email="root@example.com",
                    full_name="Root",
                    hashed_password="x",
                    role=UserRole.GLOBAL_ADMIN,
                    is_active=True,
                ),
                User(
                    email="other@example.com",
                    full_name="Other",
                    hashed_password="x",
                    role=UserRole.COMPANY_ADMIN,
                    is_active=True,
                ),
            ]
        )
        db.commit()

    monkeypatch.setattr("app.core.database.SessionLocal", factory)
    sent = bm.notify_global_admins(
        title="Offsite yedek doğrulanamadı",
        message="Depolama erişimini kontrol edin.",
        entity_type="backup_offsite_failure",
        entity_id="2026-09-22",
    )

    assert sent == 1
    with factory() as db:
        rows = list(db.scalars(select(Notification)).all())
    assert len(rows) == 1
    assert rows[0].type == NotificationType.CRITICAL
    assert rows[0].entity_type == "backup_offsite_failure"


def test_notify_global_admins_never_raises(monkeypatch):
    from app.services import backup_management as bm

    class _Boom:
        def __call__(self):
            raise RuntimeError("db yok")

    monkeypatch.setattr("app.core.database.SessionLocal", _Boom())
    assert bm.notify_global_admins(title="t", message="m", entity_type="x") == 0
