"""Değişiklik talebi uygulayıcısı — beyaz liste, çakışma ve gerçek kayıt değişimi."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AuditLog,
    ChangeRequest,
    Company,
    Employee,
    User,
    UserRole,
)
from app.services import change_request as cr
from app.services.change_request_apply import ApplyConflict, ApplyError, apply_change


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        company = Company(name="A", is_active=True)
        db.add(company)
        db.flush()
        employee = Employee(company_id=company.id, full_name="Ali Veli", job_title="Eski Ünvan", is_active=True)
        db.add(employee)
        db.flush()
        requester = User(
            email="requester@example.com",
            full_name="Talep Eden",
            hashed_password="x",
            role=UserRole.COMPANY_ADMIN,
            company_id=company.id,
            is_active=True,
        )
        approver = User(
            email="approver@example.com",
            full_name="Onaylayan",
            hashed_password="x",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        verifier = User(
            email="verifier@example.com",
            full_name="Doğrulayan",
            hashed_password="x",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add_all([requester, approver, verifier])
        db.commit()
        ids = {
            "company": company.id,
            "employee": employee.id,
            "requester": requester.id,
            "approver": approver.id,
            "verifier": verifier.id,
        }
    monkeypatch.setattr("app.core.config.settings.backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr("app.core.config.settings.upload_dir", str(tmp_path / "uploads"))
    return factory, ids


def _approved_request(factory, ids, *, field="job_title", old="Eski Ünvan", new="Yeni Ünvan", entity="employee"):
    with factory() as db:
        request = cr.create_request(
            db,
            user=db.get(User, ids["requester"]),
            payload={
                "target_entity_type": entity,
                "target_entity_id": str(ids["employee"]),
                "field_name": field,
                "old_value": old,
                "requested_value": new,
                "justification": "Talep gerekçesi yeterince uzun ve açıklayıcıdır.",
                "company_id": ids["company"],
            },
        )
        cr.verify_request(db, request_id=request.id, user=db.get(User, ids["verifier"]))
        cr.approve_request(db, request_id=request.id, user=db.get(User, ids["approver"]))
        return request.id


def test_apply_updates_real_record(setup):
    factory, ids = setup
    request_id = _approved_request(factory, ids)
    with factory() as db:
        # Onaylayan uygulayamaz; farklı bir aktör gerekiyor.
        requester = db.get(User, ids["requester"])
        requester.role = UserRole.GLOBAL_ADMIN
        db.commit()
    with factory() as db:
        final = cr.apply_request(db, request_id=request_id, user=db.get(User, ids["requester"]), applier=apply_change)
    assert final.status == "applied"
    with factory() as db:
        employee = db.get(Employee, ids["employee"])
        assert employee.job_title == "Yeni Ünvan"


def test_apply_rejects_field_outside_whitelist(setup):
    factory, ids = setup
    request_id = _approved_request(factory, ids, field="national_id_masked", old=None, new="12345678901")
    with factory() as db:
        db.get(User, ids["requester"]).role = UserRole.GLOBAL_ADMIN
        db.commit()
    with factory() as db:
        with pytest.raises(ApplyError) as error:
            cr.apply_request(db, request_id=request_id, user=db.get(User, ids["requester"]), applier=apply_change)
    assert "beyaz liste" in str(error.value)


def test_apply_rejects_unknown_entity_type(setup):
    factory, ids = setup
    request_id = _approved_request(factory, ids, entity="bilinmeyen")
    with factory() as db:
        db.get(User, ids["requester"]).role = UserRole.GLOBAL_ADMIN
        db.commit()
    with factory() as db:
        with pytest.raises(ApplyError) as error:
            cr.apply_request(db, request_id=request_id, user=db.get(User, ids["requester"]), applier=apply_change)
    assert "değiştirilemez" in str(error.value)


def test_apply_detects_conflict(setup):
    factory, ids = setup
    request_id = _approved_request(factory, ids)
    # Arada başkası kaydı değiştirdi.
    with factory() as db:
        db.get(Employee, ids["employee"]).job_title = "Üçüncü Şahıs Değiştirdi"
        db.commit()
    with factory() as db:
        db.get(User, ids["requester"]).role = UserRole.GLOBAL_ADMIN
        db.commit()
    with factory() as db:
        with pytest.raises(ApplyConflict):
            cr.apply_request(db, request_id=request_id, user=db.get(User, ids["requester"]), applier=apply_change)


def test_apply_rolls_back_status_on_error(setup):
    factory, ids = setup
    request_id = _approved_request(factory, ids, field="national_id_masked", old=None, new="1")
    with factory() as db:
        db.get(User, ids["requester"]).role = UserRole.GLOBAL_ADMIN
        db.commit()
    with factory() as db:
        with pytest.raises(ApplyError):
            cr.apply_request(db, request_id=request_id, user=db.get(User, ids["requester"]), applier=apply_change)
    with factory() as db:
        assert db.get(ChangeRequest, request_id).status == "approved"


def test_apply_writes_audit(setup):
    factory, ids = setup
    request_id = _approved_request(factory, ids)
    with factory() as db:
        db.get(User, ids["requester"]).role = UserRole.GLOBAL_ADMIN
        db.commit()
    with factory() as db:
        cr.apply_request(db, request_id=request_id, user=db.get(User, ids["requester"]), applier=apply_change)
    with factory() as db:
        rows = list(db.scalars(select(AuditLog).where(AuditLog.action == "change_request_applied")).all())
    assert len(rows) == 1
    assert rows[0].new_value and "employee" in rows[0].new_value


def test_apply_rejects_missing_target(setup):
    factory, ids = setup
    request_id = _approved_request(factory, ids)
    with factory() as db:
        db.get(User, ids["requester"]).role = UserRole.GLOBAL_ADMIN
        db.commit()
    with factory() as db:
        request = db.get(ChangeRequest, request_id)
        request.target_entity_id = "999999"
        db.commit()
    with factory() as db:
        with pytest.raises(ApplyError) as error:
            cr.apply_request(db, request_id=request_id, user=db.get(User, ids["requester"]), applier=apply_change)
    assert "bulunamadı" in str(error.value)


def test_apply_coerces_boolean_field(setup):
    factory, ids = setup
    request_id = _approved_request(factory, ids, field="is_active", old="True", new="false")
    with factory() as db:
        db.get(User, ids["requester"]).role = UserRole.GLOBAL_ADMIN
        db.commit()
    with factory() as db:
        cr.apply_request(db, request_id=request_id, user=db.get(User, ids["requester"]), applier=apply_change)
    with factory() as db:
        assert db.get(Employee, ids["employee"]).is_active is False


def test_apply_rejects_invalid_date(setup):
    factory, ids = setup
    request_id = _approved_request(factory, ids, field="start_date", old=None, new="tarih-değil")
    with factory() as db:
        db.get(User, ids["requester"]).role = UserRole.GLOBAL_ADMIN
        db.commit()
    with factory() as db:
        with pytest.raises(ApplyError) as error:
            cr.apply_request(db, request_id=request_id, user=db.get(User, ids["requester"]), applier=apply_change)
    assert "tarih" in str(error.value)


def test_apply_rejects_cross_company_target(setup):
    factory, ids = setup
    request_id = _approved_request(factory, ids)
    with factory() as db:
        db.get(User, ids["requester"]).role = UserRole.GLOBAL_ADMIN
        db.commit()
    with factory() as db:
        request = db.get(ChangeRequest, request_id)
        request.company_id = 424242
        db.commit()
    with factory() as db:
        with pytest.raises(ApplyError) as error:
            cr.apply_request(db, request_id=request_id, user=db.get(User, ids["requester"]), applier=apply_change)
    assert "kapsamında" in str(error.value)
