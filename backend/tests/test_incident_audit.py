"""Olay kayıtları denetim + kalıcı silme koruması."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.incidents import create_incident, delete_incident, update_incident
from app.core.database import Base, get_db
from app.models.entities import (
    AuditLog,
    Company,
    IncidentEvent,
    User,
    UserRole,
)
from app.schemas.incident import IncidentCreate, IncidentUpdate


class _FakeRequest:
    def __init__(self):
        from types import SimpleNamespace

        self.client = SimpleNamespace(host="127.0.0.1")
        self.headers = {"user-agent": "pytest-client"}


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        company = Company(name="A", is_active=True)
        db.add(company)
        db.flush()
        user = User(
            email="manager@example.com",
            full_name="Manager",
            hashed_password="x",
            role=UserRole.SAFETY_SPECIALIST,
            company_id=company.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        ids = (company.id, user.id)
    monkeypatch.setattr("app.api.incidents.ensure_company_access", lambda db, u, cid: None)
    monkeypatch.setattr("app.core.config.settings.backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr("app.core.config.settings.upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr("app.core.config.settings.backup_encryption_key", "")
    monkeypatch.setattr("app.core.config.settings.backup_encryption_secret_fallback", False)
    monkeypatch.setattr("app.core.config.settings.backup_encryption_force_off", False)
    return factory, ids


def _audits(factory, action: str) -> list[AuditLog]:
    with factory() as db:
        return list(
            db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)).all()
        )


def _create_incident(factory, company_id: int, user_id: int, **overrides) -> IncidentEvent:
    payload = IncidentCreate(
        company_id=company_id,
        event_type="ramak_kala",
        short_summary="Kısa ve anlamlı bir olay özet metni yazıldı.",
        event_date=date.today(),
        location="Atölye",
        detail="Olay detay metni yeterince uzun ve anlamlı.",
        classification="Tehlikeli durum",
    )
    payload = payload.model_copy(update=overrides)
    with factory() as db:
        return create_incident(payload, _FakeRequest(), db, db.get(User, user_id))


def test_create_incident_writes_audit(setup):
    factory, (company_id, user_id) = setup
    row = _create_incident(factory, company_id, user_id)
    rows = _audits(factory, "incident_created")
    assert len(rows) == 1
    assert rows[0].company_id == company_id
    assert rows[0].entity_id == str(row.id)
    assert rows[0].new_value and "form_no" in rows[0].new_value


def test_update_incident_writes_old_and_new(setup):
    factory, (company_id, user_id) = setup
    row = _create_incident(factory, company_id, user_id)
    payload = IncidentUpdate(status="Kapandı")
    with factory() as db:
        update_incident(row.id, payload, _FakeRequest(), db, db.get(User, user_id))
    rows = _audits(factory, "incident_updated")
    assert len(rows) == 1
    assert rows[0].old_value and "status" in rows[0].old_value
    assert rows[0].new_value and "Kapandı" in rows[0].new_value


def test_delete_requires_reason():
    from app.api.incidents import require_delete_reason

    with pytest.raises(HTTPException) as error:
        require_delete_reason(None)
    assert error.value.status_code == 422
    assert "gerekçe" in str(error.value.detail).lower()

    with pytest.raises(HTTPException) as error:
        require_delete_reason("kısa")
    assert error.value.status_code == 422


def test_delete_dry_run_does_not_remove(setup):
    factory, (company_id, user_id) = setup
    row = _create_incident(factory, company_id, user_id)
    with factory() as db:
        result = delete_incident(
            row.id,
            _FakeRequest(),
            reason="Olay kaydı hatalı kayıtlendi ve resmi bildirim yapıldı.",
            dry_run=True,
            db=db,
            user=db.get(User, user_id),
        )
        assert result["dry_run"] is True
        assert db.get(IncidentEvent, row.id) is not None


def test_delete_archives_before_hard_delete(setup):
    factory, (company_id, user_id) = setup
    row = _create_incident(factory, company_id, user_id)
    with factory() as db:
        response = delete_incident(
            row.id,
            _FakeRequest(),
            reason="Olay kaydı hatalı kayıtlendi ve resmi bildirim yapıldı.",
            dry_run=False,
            db=db,
            user=db.get(User, user_id),
        )
        assert response["ok"] is True
        assert db.get(IncidentEvent, row.id) is None

    rows = _audits(factory, "incident_hard_deleted")
    assert len(rows) == 1
    assert rows[0].company_id == company_id
    assert rows[0].old_value and "form_no" in rows[0].old_value
    assert rows[0].new_value and "deleted" in rows[0].new_value
    with factory() as db:
        from app.models.entities import EisaArchiveRecord

        archived = list(
            db.scalars(select(EisaArchiveRecord).where(EisaArchiveRecord.kind == "deleted_file")).all()
        )
    assert archived
    assert archived[0].entity_type == "incident_hard_delete"


def test_audit_log_has_company_id(setup):
    factory, (company_id, user_id) = setup
    _create_incident(factory, company_id, user_id)
    rows = _audits(factory, "incident_created")
    assert rows[0].company_id == company_id


def test_audit_records_request_ip_and_user_agent(setup):
    factory, (company_id, user_id) = setup
    _create_incident(factory, company_id, user_id)
    rows = _audits(factory, "incident_created")
    assert rows[0].ip_address == "127.0.0.1"
    assert rows[0].user_agent == "pytest-client"