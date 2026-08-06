from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.personnel_profile_config import personnel_profile_settings
from app.models import entities  # noqa: F401
from app.models import personnel_profile  # noqa: F401
from app.models import personnel_profile_document  # noqa: F401
from app.models.entities import (
    Company,
    Employee,
    IsgProfessional,
    OsgbOrganization,
    ProfessionalType,
    User,
    UserRole,
)
from app.models.personnel_profile import PersonnelProfile, PersonnelProfileContact
from app.models.personnel_profile_document import PersonnelProfileDocument
from app.schemas.personnel_profile import PersonnelContactVersionCreate
from app.services.personnel_profile_core import append_contact_version
from app.services.personnel_profile_osgb_scope import (
    initialize_osgb_professional_profile,
    install_osgb_service_overrides,
    list_osgb_professionals,
    professional_summary,
)


@pytest.fixture(scope="module", autouse=True)
def _install_scope_metadata():
    install_osgb_service_overrides()


@pytest.fixture()
def enabled_osgb_scope(monkeypatch):
    monkeypatch.setattr(personnel_profile_settings, "personnel_profile_card_enabled", True)
    monkeypatch.setattr(personnel_profile_settings, "personnel_profile_card_force_off", False)
    monkeypatch.setattr(personnel_profile_settings, "personnel_profile_card_pilot_osgb_ids", "35")
    monkeypatch.setattr(personnel_profile_settings, "personnel_profile_card_pilot_company_ids", "")


@pytest.fixture()
def db(enabled_osgb_scope):
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed(db: Session):
    osgb = OsgbOrganization(id=35, name="BOZKIR OSGB", is_active=True)
    other_osgb = OsgbOrganization(id=36, name="BAŞKA OSGB", is_active=True)
    db.add_all([osgb, other_osgb])
    db.flush()

    workplace = Company(id=118, name="AYAN ACADEMY", osgb_id=osgb.id, is_active=True)
    db.add(workplace)
    db.flush()
    employee = Employee(
        company_id=workplace.id,
        full_name="Ali Yıldırım",
        job_title="Operatör",
        is_active=True,
    )
    db.add(employee)

    admin = User(
        email="osgb-admin@example.com",
        full_name="OSGB Yönetici",
        hashed_password="hash",
        role=UserRole.COMPANY_ADMIN,
        osgb_id=osgb.id,
        is_active=True,
    )
    other_admin = User(
        email="other-admin@example.com",
        full_name="Başka OSGB Yönetici",
        hashed_password="hash",
        role=UserRole.COMPANY_ADMIN,
        osgb_id=other_osgb.id,
        is_active=True,
    )
    db.add_all([admin, other_admin])
    db.flush()

    specialist = IsgProfessional(
        osgb_id=osgb.id,
        full_name="Eflatun Bozkır",
        professional_type=ProfessionalType.SAFETY_SPECIALIST,
        certificate_number="UZM-35",
        is_active=True,
    )
    physician_without_assignment = IsgProfessional(
        osgb_id=osgb.id,
        full_name="Gönül Bozkır",
        professional_type=ProfessionalType.WORKPLACE_PHYSICIAN,
        certificate_number="HEK-35",
        is_active=True,
    )
    other_health = IsgProfessional(
        osgb_id=osgb.id,
        full_name="DSP Personeli",
        professional_type=ProfessionalType.OTHER_HEALTH_PERSONNEL,
        certificate_number="DSP-35",
        is_active=True,
    )
    inactive = IsgProfessional(
        osgb_id=osgb.id,
        full_name="Pasif Uzman",
        professional_type=ProfessionalType.SAFETY_SPECIALIST,
        certificate_number="PASIF-35",
        is_active=False,
    )
    other_osgb_professional = IsgProfessional(
        osgb_id=other_osgb.id,
        full_name="Başka OSGB Uzmanı",
        professional_type=ProfessionalType.SAFETY_SPECIALIST,
        certificate_number="UZM-36",
        is_active=True,
    )
    db.add_all(
        [
            specialist,
            physician_without_assignment,
            other_health,
            inactive,
            other_osgb_professional,
        ]
    )
    db.commit()
    return {
        "osgb": osgb,
        "workplace": workplace,
        "employee": employee,
        "admin": admin,
        "other_admin": other_admin,
        "specialist": specialist,
        "physician": physician_without_assignment,
        "other_health": other_health,
        "other_osgb_professional": other_osgb_professional,
    }


def test_metadata_separates_workplace_employee_and_osgb_professional_scope():
    assert PersonnelProfile.__table__.c.company_id.nullable is True
    assert PersonnelProfileContact.__table__.c.company_id.nullable is True
    assert PersonnelProfileDocument.__table__.c.company_id.nullable is True
    constraints = {constraint.name for constraint in PersonnelProfile.__table__.constraints}
    assert "uq_personnel_profile_osgb_professional" in constraints
    assert "uq_personnel_profile_company_professional" not in constraints


def test_osgb_list_contains_only_own_active_ohs_professionals_without_assignment(db: Session):
    seeded = _seed(db)
    rows = list_osgb_professionals(
        db,
        user=seeded["admin"],
        osgb_id=seeded["osgb"].id,
    )
    assert {row.full_name for row in rows} == {
        "Eflatun Bozkır",
        "Gönül Bozkır",
        "DSP Personeli",
    }
    assert seeded["physician"].id in {row.id for row in rows}
    assert seeded["employee"].full_name not in {row.full_name for row in rows}
    assert seeded["other_osgb_professional"].id not in {row.id for row in rows}


def test_professional_profile_is_osgb_scoped_idempotent_and_not_workplace_scoped(db: Session):
    seeded = _seed(db)
    profile, created = initialize_osgb_professional_profile(
        db,
        user=seeded["admin"],
        professional_id=seeded["physician"].id,
    )
    db.commit()
    assert created is True
    assert profile.osgb_id == seeded["osgb"].id
    assert profile.company_id is None
    assert profile.professional_id == seeded["physician"].id
    assert profile.employee_id is None

    same, created_again = initialize_osgb_professional_profile(
        db,
        user=seeded["admin"],
        professional_id=seeded["physician"].id,
    )
    assert created_again is False
    assert same.id == profile.id

    contact, contact_created = append_contact_version(
        db,
        user=seeded["admin"],
        profile_id=profile.id,
        payload=PersonnelContactVersionCreate(
            contact_type="corporate_email",
            contact_value="hekim@bozkir-osgb.test",
        ),
    )
    db.commit()
    assert contact_created is True
    assert contact.company_id is None

    summary = professional_summary(
        db,
        user=seeded["admin"],
        professional_id=seeded["physician"].id,
    )
    assert summary["scope"]["osgb_id"] == seeded["osgb"].id
    assert summary["scope"]["company_id"] is None
    assert summary["profile"]["active_assignment_count"] == 0


def test_other_osgb_cannot_access_professional_cards(db: Session):
    seeded = _seed(db)
    with pytest.raises(HTTPException) as exc:
        list_osgb_professionals(
            db,
            user=seeded["other_admin"],
            osgb_id=seeded["osgb"].id,
        )
    assert exc.value.status_code == 403


def test_employee_profile_rows_remain_historical_and_are_not_selected_as_osgb_professionals(db: Session):
    seeded = _seed(db)
    employee_profile = PersonnelProfile(
        osgb_id=seeded["osgb"].id,
        company_id=seeded["workplace"].id,
        subject_type="employee",
        employee_id=seeded["employee"].id,
        professional_id=None,
        status="active",
        created_by_id=seeded["admin"].id,
    )
    db.add(employee_profile)
    db.commit()
    assert employee_profile.company_id == 118
    assert db.scalar(
        select(PersonnelProfile).where(
            PersonnelProfile.subject_type == "professional",
            PersonnelProfile.employee_id == seeded["employee"].id,
        )
    ) is None
