from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import entities  # noqa: F401
from app.models import personnel_profile  # noqa: F401
from app.models.entities import (
    Branch,
    Company,
    Employee,
    OsgbOrganization,
    User,
    UserRole,
)
from app.models.personnel_profile import (
    PersonnelProfileContact,
    PersonnelProfileExperience,
)
from app.schemas.personnel_profile import (
    PersonnelContactVersionCreate,
    PersonnelExperienceVersionCreate,
    PersonnelProfileInitialize,
)
from app.services.personnel_profile_core import (
    append_contact_version,
    append_experience_version,
    initialize_personnel_profile,
    profile_snapshot,
)
from app.services.personnel_profile_management import archive_profile_entry_version


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _profile_scope(db: Session):
    osgb = OsgbOrganization(name="Test OSGB", is_active=True)
    db.add(osgb)
    db.flush()
    company = Company(
        name="Test İşyerim",
        osgb_id=osgb.id,
        is_active=True,
        hazard_class="Tehlikeli",
    )
    db.add(company)
    db.flush()
    branch = Branch(company_id=company.id, name="Merkez", is_active=True)
    db.add(branch)
    db.flush()
    admin = User(
        email="admin@example.com",
        full_name="Test Yönetici",
        hashed_password="hash",
        role=UserRole.COMPANY_ADMIN,
        company_id=company.id,
        osgb_id=osgb.id,
        is_active=True,
    )
    outsider = User(
        email="readonly@example.com",
        full_name="Salt Okunur",
        hashed_password="hash",
        role=UserRole.READ_ONLY,
        company_id=company.id,
        osgb_id=osgb.id,
        is_active=True,
    )
    employee = Employee(
        company_id=company.id,
        branch_id=branch.id,
        full_name="Ayşe Yılmaz",
        national_id_masked="12345678990",
        job_title="Kaynakçı",
        is_active=True,
    )
    db.add_all([admin, outsider, employee])
    db.flush()
    profile, _ = initialize_personnel_profile(
        db,
        user=admin,
        payload=PersonnelProfileInitialize(
            company_id=company.id,
            subject_type="employee",
            subject_id=employee.id,
            branch_id=branch.id,
        ),
    )
    db.commit()
    return company, admin, outsider, profile


def test_contact_archive_creates_new_version_without_physical_delete(db: Session):
    _, admin, _, profile = _profile_scope(db)
    first, _ = append_contact_version(
        db,
        user=admin,
        profile_id=profile.id,
        payload=PersonnelContactVersionCreate(
            contact_type="corporate_email",
            contact_value="ayse@example.com",
            visibility="internal_only",
        ),
    )
    db.commit()

    archived, created = archive_profile_entry_version(
        db,
        user=admin,
        profile_id=profile.id,
        entry_type="contacts",
        entry_key=first.entry_key,
        reason="Kurumsal e-posta kullanım dışı kaldı",
    )
    db.commit()

    assert created is True
    assert archived.version == 2
    assert archived.supersedes_id == first.id
    assert archived.lifecycle_status == "archived"
    assert archived.contact_value == "ayse@example.com"
    assert db.scalar(select(func.count()).select_from(PersonnelProfileContact)) == 2

    snapshot = profile_snapshot(db, profile)
    assert snapshot["contacts"][0]["lifecycle_status"] == "archived"
    assert snapshot["contacts"][0]["version"] == 2


def test_archive_is_idempotent_and_does_not_add_third_version(db: Session):
    _, admin, _, profile = _profile_scope(db)
    first, _ = append_experience_version(
        db,
        user=admin,
        profile_id=profile.id,
        payload=PersonnelExperienceVersionCreate(
            organization_name="Örnek Kurum",
            position="İSG Uzmanı",
        ),
    )
    db.commit()

    second, created = archive_profile_entry_version(
        db,
        user=admin,
        profile_id=profile.id,
        entry_type="experiences",
        entry_key=first.entry_key,
        reason="Deneyim kaydı arşivlendi",
    )
    db.commit()
    same, second_created = archive_profile_entry_version(
        db,
        user=admin,
        profile_id=profile.id,
        entry_type="experiences",
        entry_key=first.entry_key,
        reason="Tekrar gönderim kontrolü",
    )

    assert created is True
    assert second_created is False
    assert same.id == second.id
    assert db.scalar(select(func.count()).select_from(PersonnelProfileExperience)) == 2


def test_read_only_role_cannot_archive_profile_entries(db: Session):
    _, admin, outsider, profile = _profile_scope(db)
    first, _ = append_contact_version(
        db,
        user=admin,
        profile_id=profile.id,
        payload=PersonnelContactVersionCreate(
            contact_type="business_phone",
            contact_value="05550000000",
        ),
    )
    db.commit()

    with pytest.raises(HTTPException) as exc:
        archive_profile_entry_version(
            db,
            user=outsider,
            profile_id=profile.id,
            entry_type="contacts",
            entry_key=first.entry_key,
            reason="Yetkisiz arşiv denemesi",
        )
    assert exc.value.status_code == 403


def test_unknown_entry_type_is_rejected_without_mutation(db: Session):
    _, admin, _, profile = _profile_scope(db)
    with pytest.raises(HTTPException) as exc:
        archive_profile_entry_version(
            db,
            user=admin,
            profile_id=profile.id,
            entry_type="documents",
            entry_key="00000000-0000-0000-0000-000000000000",
            reason="Geçersiz tür",
        )
    assert exc.value.status_code == 404
