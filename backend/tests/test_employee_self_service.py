from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base
from app.models import entities  # noqa: F401
from app.models import remote_training as _remote_training_models  # noqa: F401
from app.models.entities import (
    Company,
    Employee,
    HealthFitnessStatus,
    HealthRecord,
    HealthRecordType,
    OsgbOrganization,
    User,
    UserRole,
)
from app.models.remote_training import RemoteTrainingEmployeeAccess
from app.api.self_service import (
    _assert_self_service_user,
    _resolve_employee_scope,
    build_self_service_payload,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed(db: Session):
    osgb = OsgbOrganization(name="Self Servis OSGB", is_active=True)
    other_osgb = OsgbOrganization(name="Diğer OSGB", is_active=True)
    db.add_all([osgb, other_osgb])
    db.flush()

    company = Company(name="Self Servis İşyeri", osgb_id=osgb.id, is_active=True)
    other_company = Company(name="Başka İşyeri", osgb_id=other_osgb.id, is_active=True)
    db.add_all([company, other_company])
    db.flush()

    employee = Employee(
        company_id=company.id,
        full_name="Ayşe Yılmaz",
        job_title="Kaynakçı",
        department="Üretim",
        start_date=date(2024, 1, 15),
        is_active=True,
    )
    db.add(employee)
    db.flush()

    user = User(
        email="ayse.employee@example.com",
        full_name="Ayşe Yılmaz",
        hashed_password="hash",
        role=UserRole.READ_ONLY,
        company_id=company.id,
        osgb_id=osgb.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    mapping = RemoteTrainingEmployeeAccess(
        company_id=company.id,
        osgb_id=osgb.id,
        user_id=user.id,
        employee_id=employee.id,
        is_active=True,
    )
    db.add(mapping)
    db.flush()
    return osgb, company, other_company, employee, user, mapping


def test_self_service_is_fail_closed_by_default(db: Session, monkeypatch):
    _, _, _, _, user, _ = _seed(db)
    monkeypatch.setattr(settings, "employee_self_service_enabled", False)
    monkeypatch.setattr(settings, "employee_self_service_force_off", False)

    with pytest.raises(HTTPException) as exc:
        _assert_self_service_user(user)
    assert exc.value.status_code == 404


def test_self_service_is_read_only_role_only(db: Session, monkeypatch):
    _, company, _, _, _, _ = _seed(db)
    admin = User(
        email="admin.self-service@example.com",
        full_name="OSGB Yönetici",
        hashed_password="hash",
        role=UserRole.COMPANY_ADMIN,
        company_id=company.id,
        is_active=True,
    )
    db.add(admin)
    db.flush()
    monkeypatch.setattr(settings, "employee_self_service_enabled", True)
    monkeypatch.setattr(settings, "employee_self_service_force_off", False)

    with pytest.raises(HTTPException) as exc:
        _assert_self_service_user(admin)
    assert exc.value.status_code == 403


def test_self_service_uses_explicit_mapping_and_minimizes_health_data(db: Session, monkeypatch):
    osgb, company, other_company, employee, user, mapping = _seed(db)
    monkeypatch.setattr(settings, "employee_self_service_enabled", True)
    monkeypatch.setattr(settings, "employee_self_service_force_off", False)

    _, resolved_company, resolved_employee, branch = _resolve_employee_scope(db, user)
    assert resolved_company.id == company.id
    assert resolved_employee.id == employee.id
    assert branch is None

    health = HealthRecord(
        company_id=company.id,
        employee_id=employee.id,
        record_type=HealthRecordType.PERIODIC_EXAM,
        examination_date=date(2026, 1, 10),
        next_examination_date=date(2027, 1, 10),
        fitness_status=HealthFitnessStatus.FIT,
        summary="klinik özet gizli",
        confidential_note="gizli not",
        restrictions="gizli kısıt",
        created_by_id=user.id,
    )
    db.add(health)
    db.flush()
    payload = build_self_service_payload(
        db,
        user=user,
        company=resolved_company,
        employee=resolved_employee,
        branch=branch,
    )
    assert payload["scope"]["company_id"] == company.id
    assert payload["employee"]["id"] == employee.id
    assert payload["health"]["next_examination_date"] == "2027-01-10"
    assert payload["health"]["details_included"] is False
    assert "confidential_note" not in payload["health"]
    assert "fitness_status" not in payload["health"]
    assert payload["privacy"]["cross_employee_data"] is False
    assert payload["capabilities"]["can_write"] is False

    # A company binding changed away from the explicit mapping is rejected;
    # no name-based fallback can recover access.
    user.company_id = other_company.id
    with pytest.raises(HTTPException) as exc:
        _resolve_employee_scope(db, user)
    assert exc.value.status_code == 403
    assert mapping.company_id == company.id
