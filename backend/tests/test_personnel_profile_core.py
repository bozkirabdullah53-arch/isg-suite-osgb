from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import entities  # noqa: F401
from app.models import personnel_profile  # noqa: F401
from app.models.entities import (
    AssignmentStatus,
    Branch,
    Company,
    Employee,
    IsgProfessional,
    OsgbOrganization,
    ProfessionalType,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.models.personnel_profile import (
    IMMUTABLE_PROFILE_SUBJECT_FIELDS,
    PersonnelProfile,
    PersonnelProfileCompetency,
    PersonnelProfileContact,
    PersonnelProfileExperience,
)
from app.schemas.personnel_profile import (
    PersonnelCompetencyVersionCreate,
    PersonnelContactVersionCreate,
    PersonnelExperienceVersionCreate,
    PersonnelProfileInitialize,
)
from app.services.personnel_profile_core import (
    append_competency_version,
    append_contact_version,
    append_experience_version,
    archive_personnel_profile,
    initialize_personnel_profile,
    profile_snapshot,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_scope(db: Session):
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
        email="admin@example.test",
        full_name="Test Yönetici",
        hashed_password="hash",
        role=UserRole.COMPANY_ADMIN,
        company_id=company.id,
        osgb_id=osgb.id,
        is_active=True,
    )
    field_user = User(
        email="uzman@example.test",
        full_name="Saha Uzmanı",
        hashed_password="hash",
        role=UserRole.SAFETY_SPECIALIST,
        osgb_id=osgb.id,
        is_active=True,
    )
    db.add_all([admin, field_user])
    db.flush()
    employee = Employee(
        company_id=company.id,
        branch_id=branch.id,
        full_name="Ayşe Yılmaz",
        national_id_masked="12345678990",
        job_title="Kaynakçı",
        department="Üretim",
        special_status="Engelli/Hükümlü",
        is_active=True,
    )
    professional = IsgProfessional(
        osgb_id=osgb.id,
        full_name="Saha Uzmanı",
        email="uzman@example.test",
        professional_type=ProfessionalType.SAFETY_SPECIALIST,
        certificate_class="A",
        certificate_number="UZM-1",
        is_active=True,
    )
    db.add_all([employee, professional])
    db.flush()
    return osgb, company, branch, admin, field_user, employee, professional


def _employee_profile(db: Session):
    osgb, company, branch, admin, field_user, employee, professional = _seed_scope(db)
    payload = PersonnelProfileInitialize(
        company_id=company.id,
        subject_type="employee",
        subject_id=employee.id,
        branch_id=branch.id,
    )
    profile, created = initialize_personnel_profile(db, user=admin, payload=payload)
    db.commit()
    return osgb, company, branch, admin, field_user, employee, professional, profile, created


def test_models_are_isolated_append_only_and_contain_no_restricted_columns():
    assert PersonnelProfile.__table__.name == "personnel_profiles"
    assert PersonnelProfileContact.__table__.name == "personnel_profile_contacts"
    assert PersonnelProfileCompetency.__table__.name == "personnel_profile_competencies"
    assert PersonnelProfileExperience.__table__.name == "personnel_profile_experiences"

    assert {"osgb_id", "company_id", "employee_id", "professional_id"} <= set(
        PersonnelProfile.__table__.columns.keys()
    )
    assert "employee_id" in IMMUTABLE_PROFILE_SUBJECT_FIELDS
    assert "professional_id" in IMMUTABLE_PROFILE_SUBJECT_FIELDS

    forbidden = {
        "national_id",
        "home_address",
        "emergency_contact",
        "health_data",
        "diagnosis",
        "criminal_record",
        "salary",
        "disciplinary_data",
    }
    for model in (
        PersonnelProfile,
        PersonnelProfileContact,
        PersonnelProfileCompetency,
        PersonnelProfileExperience,
    ):
        assert forbidden.isdisjoint(set(model.__table__.columns.keys()))


def test_schema_rejects_restricted_or_unknown_fields():
    with pytest.raises(ValidationError):
        PersonnelContactVersionCreate(
            contact_type="corporate_email",
            contact_value="person@example.test",
            health_data="blocked",
        )
    with pytest.raises(ValidationError):
        PersonnelExperienceVersionCreate(
            organization_name="Kurum",
            position="Uzman",
            salary="blocked",
        )
    with pytest.raises(ValidationError):
        PersonnelCompetencyVersionCreate(
            category="professional_duty",
            name="İş Güvenliği Uzmanı",
            verification_status="verified",
        )


def test_employee_profile_is_explicit_idempotent_and_does_not_backfill(db: Session):
    _, company, branch, admin, _, employee, _, profile, created = _employee_profile(db)
    assert created is True
    assert profile.company_id == company.id
    assert profile.branch_id == branch.id
    assert profile.employee_id == employee.id
    assert profile.professional_id is None
    assert profile.user_id is None

    same, second_created = initialize_personnel_profile(
        db,
        user=admin,
        payload=PersonnelProfileInitialize(
            company_id=company.id,
            subject_type="employee",
            subject_id=employee.id,
            branch_id=branch.id,
        ),
    )
    assert second_created is False
    assert same.id == profile.id
    assert db.scalar(select(func.count()).select_from(PersonnelProfile)) == 1


def test_professional_profile_requires_active_assignment(db: Session):
    _, company, _, admin, _, _, professional = _seed_scope(db)
    payload = PersonnelProfileInitialize(
        company_id=company.id,
        subject_type="professional",
        subject_id=professional.id,
    )
    with pytest.raises(HTTPException) as exc:
        initialize_personnel_profile(db, user=admin, payload=payload)
    assert exc.value.status_code == 409
    assert "aktif görevlendirmesi" in str(exc.value.detail)

    db.add(
        WorkplaceAssignment(
            osgb_id=professional.osgb_id,
            company_id=company.id,
            professional_id=professional.id,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            start_date=date(2026, 1, 1),
            status=AssignmentStatus.ACTIVE,
        )
    )
    db.flush()
    profile, created = initialize_personnel_profile(db, user=admin, payload=payload)
    assert created is True
    assert profile.professional_id == professional.id
    assert profile.employee_id is None


def test_database_rejects_profile_with_two_subjects(db: Session):
    osgb, company, branch, admin, _, employee, professional = _seed_scope(db)
    invalid = PersonnelProfile(
        osgb_id=osgb.id,
        company_id=company.id,
        branch_id=branch.id,
        subject_type="employee",
        employee_id=employee.id,
        professional_id=professional.id,
        status="active",
        created_by_id=admin.id,
    )
    db.add(invalid)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_profile_subject_cannot_be_changed_and_archive_is_one_way(db: Session):
    _, company, _, admin, _, _, _, profile, _ = _employee_profile(db)
    profile.company_id = company.id + 100
    with pytest.raises(ValueError, match="tenant bağlantıları"):
        db.commit()
    db.rollback()

    archive_personnel_profile(db, user=admin, profile=profile)
    db.commit()
    assert profile.status == "archived"
    profile.status = "active"
    with pytest.raises(ValueError, match="yeniden aktifleştirilemez"):
        db.commit()
    db.rollback()


def test_field_role_cannot_create_or_append_profile_data(db: Session):
    _, company, branch, _, field_user, employee, _, profile, _ = _employee_profile(db)
    with pytest.raises(HTTPException) as exc:
        initialize_personnel_profile(
            db,
            user=field_user,
            payload=PersonnelProfileInitialize(
                company_id=company.id,
                subject_type="employee",
                subject_id=employee.id,
                branch_id=branch.id,
            ),
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        append_contact_version(
            db,
            user=field_user,
            profile_id=profile.id,
            payload=PersonnelContactVersionCreate(
                contact_type="corporate_email",
                contact_value="person@example.test",
            ),
        )
    assert exc.value.status_code == 403


def test_contact_versions_are_append_only_and_duplicate_safe(db: Session):
    _, _, _, admin, _, _, _, profile, _ = _employee_profile(db)
    first, created = append_contact_version(
        db,
        user=admin,
        profile_id=profile.id,
        payload=PersonnelContactVersionCreate(
            contact_type="corporate_email",
            label="Kurumsal",
            contact_value="person@example.test",
            visibility="internal_only",
        ),
    )
    db.commit()
    assert created is True
    assert first.version == 1
    assert first.verification_status == "unverified"

    duplicate, duplicate_created = append_contact_version(
        db,
        user=admin,
        profile_id=profile.id,
        payload=PersonnelContactVersionCreate(
            entry_key=first.entry_key,
            change_reason="Tekrar gönderim kontrolü",
            contact_type="corporate_email",
            label="Kurumsal",
            contact_value="person@example.test",
            visibility="internal_only",
        ),
    )
    assert duplicate_created is False
    assert duplicate.id == first.id

    second, second_created = append_contact_version(
        db,
        user=admin,
        profile_id=profile.id,
        payload=PersonnelContactVersionCreate(
            entry_key=first.entry_key,
            change_reason="Kurumsal adres güncellendi",
            contact_type="corporate_email",
            label="Kurumsal",
            contact_value="new@example.test",
            visibility="internal_only",
        ),
    )
    db.commit()
    assert second_created is True
    assert second.version == 2
    assert second.supersedes_id == first.id
    assert db.scalar(select(func.count()).select_from(PersonnelProfileContact)) == 2

    first.contact_value = "tamper@example.test"
    with pytest.raises(ValueError, match="yeni sürüm oluşturun"):
        db.commit()
    db.rollback()


def test_competency_experience_snapshot_uses_latest_versions_only(db: Session):
    _, _, _, admin, _, _, _, profile, _ = _employee_profile(db)
    competency, _ = append_competency_version(
        db,
        user=admin,
        profile_id=profile.id,
        payload=PersonnelCompetencyVersionCreate(
            category="technical_specialization",
            name="Makine Güvenliği",
            description="İlk sürüm açıklaması",
        ),
    )
    experience, _ = append_experience_version(
        db,
        user=admin,
        profile_id=profile.id,
        payload=PersonnelExperienceVersionCreate(
            organization_name="Örnek Kurum",
            position="İSG Uzmanı",
            professional_summary="Gizli belge içermeyen profesyonel deneyim özeti.",
        ),
    )
    db.commit()

    competency_v2, _ = append_competency_version(
        db,
        user=admin,
        profile_id=profile.id,
        payload=PersonnelCompetencyVersionCreate(
            entry_key=competency.entry_key,
            change_reason="Açıklama güncellendi",
            category="technical_specialization",
            name="Makine Güvenliği",
            description="İkinci sürüm açıklaması",
        ),
    )
    experience_v2, _ = append_experience_version(
        db,
        user=admin,
        profile_id=profile.id,
        payload=PersonnelExperienceVersionCreate(
            entry_key=experience.entry_key,
            change_reason="Pozisyon güncellendi",
            organization_name="Örnek Kurum",
            position="Kıdemli İSG Uzmanı",
            professional_summary="Gizli belge içermeyen profesyonel deneyim özeti.",
        ),
    )
    db.commit()

    snapshot = profile_snapshot(db, profile)
    assert len(snapshot["competencies"]) == 1
    assert snapshot["competencies"][0]["version"] == competency_v2.version == 2
    assert snapshot["competencies"][0]["description"] == "İkinci sürüm açıklaması"
    assert len(snapshot["experiences"]) == 1
    assert snapshot["experiences"][0]["version"] == experience_v2.version == 2
    assert snapshot["experiences"][0]["position"] == "Kıdemli İSG Uzmanı"
    assert snapshot["privacy"] == {
        "ordinary_professional_data_only": True,
        "national_identity_included": False,
        "home_address_included": False,
        "emergency_contact_included": False,
        "health_data_included": False,
        "criminal_record_included": False,
        "salary_included": False,
        "disciplinary_data_included": False,
        "documents_included": False,
        "external_sharing_enabled": False,
    }


def test_archived_profile_rejects_new_versions(db: Session):
    _, _, _, admin, _, _, _, profile, _ = _employee_profile(db)
    archive_personnel_profile(db, user=admin, profile=profile)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        append_experience_version(
            db,
            user=admin,
            profile_id=profile.id,
            payload=PersonnelExperienceVersionCreate(
                organization_name="Kurum",
                position="Uzman",
            ),
        )
    assert exc.value.status_code == 409
