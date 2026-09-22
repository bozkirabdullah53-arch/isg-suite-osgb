"""Değişiklik talebi servisi — durum makinesi, 4 göz ve denetim."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AuditLog,
    ChangeRequest,
    ChangeRequestEvent,
    ChangeRequestStatus,
    Company,
    User,
    UserRole,
)
from app.services import change_request as cr


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        company = Company(name="A", is_active=True)
        db.add(company)
        db.flush()
        requester = User(
            email="requester@example.com",
            full_name="Talep Eden",
            hashed_password="x",
            role=UserRole.COMPANY_ADMIN,
            company_id=company.id,
            is_active=True,
        )
        verifier = User(
            email="verifier@example.com",
            full_name="Doğrulayan",
            hashed_password="x",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        approver = User(
            email="approver@example.com",
            full_name="Onaylayan",
            hashed_password="x",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add_all([requester, verifier, approver])
        db.commit()
        ids = {
            "company": company.id,
            "requester": requester.id,
            "verifier": verifier.id,
            "approver": approver.id,
        }
    monkeypatch.setattr("app.core.config.settings.backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr("app.core.config.settings.upload_dir", str(tmp_path / "uploads"))
    return factory, ids


def _payload(company_id: int, **overrides) -> dict:
    payload = {
        "target_entity_type": "employee",
        "target_entity_id": "1",
        "field_name": "job_title",
        "old_value": "Eski Ünvan",
        "requested_value": "Yeni Ünvan",
        "justification": "Personelin ünvanı terfi nedeniyle güncellenmelidir.",
        "company_id": company_id,
        "requester_type": "employer",
        "channel": "platform",
    }
    payload.update(overrides)
    return payload


def _create(factory, ids, **overrides) -> ChangeRequest:
    with factory() as db:
        return cr.create_request(db, user=db.get(User, ids["requester"]), payload=_payload(ids["company"], **overrides))


def _audits(factory, action: str) -> list[AuditLog]:
    with factory() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.action == action)).all())


def test_request_no_is_sequential(factory_fixture=None):
    pass


def test_create_request_generates_number(setup):
    factory, ids = setup
    first = _create(factory, ids)
    second = _create(factory, ids)
    year = datetime.utcnow().year
    assert first.request_no == f"CR-{year}-0001"
    assert second.request_no == f"CR-{year}-0002"


def test_create_requires_long_justification(setup):
    factory, ids = setup
    with factory() as db:
        with pytest.raises(cr.ChangeRequestError) as error:
            cr.create_request(db, user=db.get(User, ids["requester"]), payload=_payload(ids["company"], justification="kısa"))
    assert error.value.status_code == 422


def test_create_requires_requested_value(setup):
    factory, ids = setup
    with factory() as db:
        with pytest.raises(cr.ChangeRequestError) as error:
            cr.create_request(
                db,
                user=db.get(User, ids["requester"]),
                payload=_payload(ids["company"], requested_value="   "),
            )
    assert error.value.status_code == 422


def test_create_writes_audit_and_event(setup):
    factory, ids = setup
    row = _create(factory, ids)
    assert len(_audits(factory, "change_request_created")) == 1
    with factory() as db:
        events = list(db.scalars(select(ChangeRequestEvent).where(ChangeRequestEvent.change_request_id == row.id)).all())
    assert len(events) == 1
    assert events[0].to_status == "submitted"


def test_happy_path_transitions(setup):
    factory, ids = setup
    row = _create(factory, ids)
    with factory() as db:
        cr.verify_request(db, request_id=row.id, user=db.get(User, ids["verifier"]))
    with factory() as db:
        cr.approve_request(db, request_id=row.id, user=db.get(User, ids["approver"]))
    with factory() as db:
        final = cr.apply_request(db, request_id=row.id, user=db.get(User, ids["verifier"]))
    assert final.status == ChangeRequestStatus.APPLIED.value
    with factory() as db:
        events = list(
            db.scalars(
                select(ChangeRequestEvent)
                .where(ChangeRequestEvent.change_request_id == row.id)
                .order_by(ChangeRequestEvent.id)
            ).all()
        )
    assert [event.to_status for event in events] == ["submitted", "verified", "approved", "applied"]


def test_requester_cannot_approve_own_request(setup):
    factory, ids = setup
    row = _create(factory, ids)
    with factory() as db:
        with pytest.raises(cr.ChangeRequestError) as error:
            cr.approve_request(db, request_id=row.id, user=db.get(User, ids["requester"]))
    assert error.value.status_code == 403
    assert "4 göz" in str(error.value.detail)


def test_verifier_cannot_approve(setup):
    factory, ids = setup
    row = _create(factory, ids)
    with factory() as db:
        cr.verify_request(db, request_id=row.id, user=db.get(User, ids["verifier"]))
    with factory() as db:
        with pytest.raises(cr.ChangeRequestError) as error:
            cr.approve_request(db, request_id=row.id, user=db.get(User, ids["verifier"]))
    assert error.value.status_code == 403


def test_approver_cannot_apply(setup):
    factory, ids = setup
    row = _create(factory, ids)
    with factory() as db:
        cr.verify_request(db, request_id=row.id, user=db.get(User, ids["verifier"]))
    with factory() as db:
        cr.approve_request(db, request_id=row.id, user=db.get(User, ids["approver"]))
    with factory() as db:
        with pytest.raises(cr.ChangeRequestError) as error:
            cr.apply_request(db, request_id=row.id, user=db.get(User, ids["approver"]))
    assert error.value.status_code == 403


def test_apply_before_approve_is_rejected(setup):
    factory, ids = setup
    row = _create(factory, ids)
    with factory() as db:
        with pytest.raises(cr.ChangeRequestError) as error:
            cr.apply_request(db, request_id=row.id, user=db.get(User, ids["approver"]))
    assert error.value.status_code == 422


def test_reject_requires_reason(setup):
    factory, ids = setup
    row = _create(factory, ids)
    with factory() as db:
        with pytest.raises(cr.ChangeRequestError) as error:
            cr.reject_request(db, request_id=row.id, user=db.get(User, ids["approver"]), reason="kısa")
    assert error.value.status_code == 422


def test_reject_records_reason(setup):
    factory, ids = setup
    row = _create(factory, ids)
    with factory() as db:
        final = cr.reject_request(
            db,
            request_id=row.id,
            user=db.get(User, ids["approver"]),
            reason="Veri sahibi kimliği doğrulanamadı, talep reddedildi.",
        )
    assert final.status == ChangeRequestStatus.REJECTED.value
    assert "kimliği doğrulanamadı" in final.rejection_reason
    assert len(_audits(factory, "change_request_rejected")) == 1


def test_cancel_pending_request(setup):
    factory, ids = setup
    row = _create(factory, ids)
    with factory() as db:
        final = cr.cancel_request(db, request_id=row.id, user=db.get(User, ids["requester"]), note="Vazgeçildi.")
    assert final.status == ChangeRequestStatus.CANCELLED.value


def test_applied_request_is_terminal(setup):
    factory, ids = setup
    row = _create(factory, ids)
    with factory() as db:
        cr.verify_request(db, request_id=row.id, user=db.get(User, ids["verifier"]))
    with factory() as db:
        cr.approve_request(db, request_id=row.id, user=db.get(User, ids["approver"]))
    with factory() as db:
        cr.apply_request(db, request_id=row.id, user=db.get(User, ids["verifier"]))
    with factory() as db:
        with pytest.raises(cr.ChangeRequestError):
            cr.cancel_request(db, request_id=row.id, user=db.get(User, ids["requester"]))


def test_sla_due_is_set(setup):
    factory, ids = setup
    row = _create(factory, ids)
    assert row.sla_due_at is not None
    assert row.sla_due_at > datetime.utcnow()


def test_sla_overdue_detects_stale(setup):
    factory, ids = setup
    row = _create(factory, ids)
    with factory() as db:
        stored = db.get(ChangeRequest, row.id)
        stored.sla_due_at = datetime.utcnow() - timedelta(days=1)
        db.commit()
        overdue = cr.sla_overdue_requests(db)
    assert [item.id for item in overdue] == [row.id]


def test_list_requests_scopes_by_company(setup):
    factory, ids = setup
    _create(factory, ids)
    with factory() as db:
        rows = cr.list_requests(db, user=db.get(User, ids["requester"]))
    assert len(rows) == 1


def test_list_requests_rejects_bad_status(setup):
    factory, ids = setup
    with factory() as db:
        with pytest.raises(cr.ChangeRequestError) as error:
            cr.list_requests(db, user=db.get(User, ids["requester"]), status="bilinmeyen")
    assert error.value.status_code == 422


def test_audit_records_target_company(setup):
    factory, ids = setup
    _create(factory, ids)
    rows = _audits(factory, "change_request_created")
    assert rows[0].company_id == ids["company"]
    assert rows[0].module == "change_request"


def test_missing_request_returns_404(setup):
    factory, ids = setup
    with factory() as db:
        with pytest.raises(cr.ChangeRequestError) as error:
            cr.get_request(db, 999999)
    assert error.value.status_code == 404
