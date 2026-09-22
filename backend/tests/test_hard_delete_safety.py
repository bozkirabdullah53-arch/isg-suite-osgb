"""Kritik modül denetim kayıtları: personel ve firma mutasyonları."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import AuditLog, Company, EisaArchiveRecord, Employee, User, UserRole


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        company = Company(name="A", is_active=True)
        db.add(company)
        db.flush()
        admin = User(
            email="admin@example.com",
            full_name="Admin",
            hashed_password="x",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        ids = {"company": company.id, "admin": admin.id}
    monkeypatch.setattr("app.api.employees.ensure_company_access", lambda db, u, cid: None)
    monkeypatch.setattr("app.core.config.settings.backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr("app.core.config.settings.upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr("app.core.config.settings.backup_encryption_key", "")
    monkeypatch.setattr("app.core.config.settings.backup_encryption_secret_fallback", False)
    monkeypatch.setattr("app.core.config.settings.backup_encryption_force_off", False)
    return factory, ids


class _FakeRequest:
    def __init__(self):
        from types import SimpleNamespace

        self.client = SimpleNamespace(host="127.0.0.1")
        self.headers = {"user-agent": "pytest-client"}


def _audits(factory, action: str) -> list[AuditLog]:
    with factory() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.action == action)).all())


def _create_employee(factory, ids, **overrides) -> Employee:
    from app.api.employees import create_employee
    from app.schemas.employee import EmployeeCreate

    payload = EmployeeCreate(
        company_id=ids["company"],
        full_name=overrides.pop("full_name", "Ali Veli"),
        job_title=overrides.pop("job_title", "Operatör"),
        start_date=overrides.pop("start_date", date(2025, 1, 1)),
        **overrides,
    )
    with factory() as db:
        return create_employee(payload, _FakeRequest(), db, db.get(User, ids["admin"]))


def test_employee_create_writes_audit(setup):
    factory, ids = setup
    row = _create_employee(factory, ids)
    rows = _audits(factory, "employee_created")
    assert len(rows) == 1
    assert rows[0].company_id == ids["company"]
    assert rows[0].entity_id == str(row.id)
    assert rows[0].new_value and "Operatör" in rows[0].new_value


def test_employee_update_writes_old_and_new(setup):
    factory, ids = setup
    row = _create_employee(factory, ids)
    from app.api.employees import update_employee
    from app.schemas.employee import EmployeeUpdate

    with factory() as db:
        update_employee(
            row.id,
            EmployeeUpdate(job_title="Şef"),
            _FakeRequest(),
            db,
            db.get(User, ids["admin"]),
        )
    rows = _audits(factory, "employee_updated")
    assert len(rows) == 1
    assert "Operatör" in rows[0].old_value
    assert "Şef" in rows[0].new_value


def test_employee_deactivate_writes_audit(setup):
    factory, ids = setup
    row = _create_employee(factory, ids)
    from app.api.employees import deactivate_employee

    with factory() as db:
        deactivate_employee(row.id, _FakeRequest(), db, db.get(User, ids["admin"]))
    assert len(_audits(factory, "employee_deactivated")) == 1


def test_bulk_deactivate_dry_run_changes_nothing(setup):
    factory, ids = setup
    first = _create_employee(factory, ids, full_name="Ali Veli")
    second = _create_employee(factory, ids, full_name="Ayşe Yılmaz")
    from app.api.employees import bulk_deactivate_employees

    with factory() as db:
        result = bulk_deactivate_employees(
            _FakeRequest(),
            employee_ids=[first.id, second.id],
            company_id=ids["company"],
            exit_date=None,
            reason="Toplu çıkış",
            dry_run=True,
            db=db,
            user=db.get(User, ids["admin"]),
        )
    assert result["dry_run"] is True
    assert result["would_change"] == 2
    with factory() as db:
        assert db.get(Employee, first.id).is_active is True
        assert db.get(Employee, second.id).is_active is True


def test_bulk_deactivate_writes_audit(setup):
    factory, ids = setup
    row = _create_employee(factory, ids)
    from app.api.employees import bulk_deactivate_employees

    with factory() as db:
        bulk_deactivate_employees(
            _FakeRequest(),
            employee_ids=[row.id],
            company_id=ids["company"],
            exit_date=None,
            reason="Toplu çıkış",
            dry_run=False,
            db=db,
            user=db.get(User, ids["admin"]),
        )
    rows = _audits(factory, "employees_bulk_deactivated")
    assert len(rows) == 1
    assert rows[0].company_id == ids["company"]
    assert "Toplu çıkış" in rows[0].description


def test_bulk_purge_requires_reason(setup):
    factory, ids = setup
    row = _create_employee(factory, ids)
    from app.api.employees import bulk_purge_inactive_employees
    from fastapi import HTTPException

    with factory() as db:
        with pytest.raises(HTTPException) as error:
            bulk_purge_inactive_employees(
                _FakeRequest(),
                employee_ids=[row.id],
                company_id=ids["company"],
                reason=None,
                dry_run=False,
                db=db,
                user=db.get(User, ids["admin"]),
            )
    assert error.value.status_code == 422
    with factory() as db:
        assert db.get(Employee, row.id) is not None


def test_bulk_purge_dry_run_changes_nothing(setup):
    factory, ids = setup
    row = _create_employee(factory, ids)
    from app.api.employees import bulk_purge_inactive_employees

    with factory() as db:
        result = bulk_purge_inactive_employees(
            _FakeRequest(),
            employee_ids=[row.id],
            company_id=ids["company"],
            reason="Yanlış kayıt",
            dry_run=True,
            db=db,
            user=db.get(User, ids["admin"]),
        )
    assert result["dry_run"] is True
    assert result["would_delete"] == 1
    with factory() as db:
        assert db.get(Employee, row.id) is not None


def test_bulk_purge_archives_and_audits(setup):
    factory, ids = setup
    row = _create_employee(factory, ids)
    from app.api.employees import bulk_purge_inactive_employees

    with factory() as db:
        result = bulk_purge_inactive_employees(
            _FakeRequest(),
            employee_ids=[row.id],
            company_id=ids["company"],
            reason="Mükerrer kayıt, resmi bildirim yok.",
            dry_run=False,
            db=db,
            user=db.get(User, ids["admin"]),
        )
    assert result["deleted"] == 1
    with factory() as db:
        assert db.get(Employee, row.id) is None
    rows = _audits(factory, "employees_bulk_purged")
    assert len(rows) == 1
    assert "Mükerrer kayıt" in rows[0].description
    with factory() as db:
        archived = list(
            db.scalars(select(EisaArchiveRecord).where(EisaArchiveRecord.entity_type == "employee_bulk_purge")).all()
        )
    assert archived


def test_employee_audit_records_actor_ip(setup):
    factory, ids = setup
    _create_employee(factory, ids)
    rows = _audits(factory, "employee_created")
    assert rows[0].ip_address == "127.0.0.1"
    assert rows[0].user_agent == "pytest-client"
    assert rows[0].user_id == ids["admin"]


def test_company_purge_archives_audit_chain(setup):
    """Purge öncesi EYAS/e-imza/sağlık denetim izleri arşive yazılmalı."""
    factory, ids = setup
    from app.api.companies import _archive_audit_chain_before_purge
    from app.models.entities import EyasEvent, EyasWorkflow

    with factory() as db:
        workflow = EyasWorkflow(company_id=ids["company"], title="Test", status="open", created_by_id=ids["admin"])
        db.add(workflow)
        db.flush()
        db.add(
            EyasEvent(
                company_id=ids["company"],
                workflow_id=workflow.id,
                actor_user_id=None,
                action="test_event",
                payload_json="{}",
                event_hash="a" * 64,
            )
        )
        db.commit()
        archived = _archive_audit_chain_before_purge(db, ids["company"])
        db.commit()

    assert archived.get("eyas_event") == 1
    with factory() as db:
        rows = list(
            db.scalars(
                select(EisaArchiveRecord).where(EisaArchiveRecord.entity_type == "purge_eyas_event")
            ).all()
        )
    assert rows
    assert rows[0].company_id == ids["company"]
