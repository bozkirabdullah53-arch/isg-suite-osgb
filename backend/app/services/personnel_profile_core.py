"""Dijital Personel Kartı Faz 3 çekirdek servisi.

- Mevcut Employee/IsgProfessional/User kayıtlarını taşımaz veya birleştirmez.
- Profil öznesi açık ve şirket kapsamlıdır.
- İletişim, yeterlilik ve deneyim değişiklikleri yeni sürüm satırı oluşturur.
- Restricted veri, dosya, CV veya dış paylaşım işlemez.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, TypeVar
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.models.entities import (
    AssignmentStatus,
    Branch,
    Company,
    Employee,
    IsgProfessional,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.models.personnel_profile import (
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
from app.services.audit import add_audit_log


PROFILE_WRITE_ROLES = {UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN}
VersionModel = TypeVar(
    "VersionModel",
    PersonnelProfileContact,
    PersonnelProfileCompetency,
    PersonnelProfileExperience,
)


def require_profile_write_role(user: User) -> None:
    if user.role not in PROFILE_WRITE_ROLES:
        raise HTTPException(
            403,
            "Personel profil kaydı oluşturma veya sürüm ekleme yetkiniz yok.",
        )


def _company_for_profile(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "İşyeri bulunamadı.")
    if not company.osgb_id:
        raise HTTPException(
            409,
            "İşyeri bir OSGB kapsamına bağlı olmadığı için personel profili oluşturulamaz.",
        )
    return company


def _validate_branch(db: Session, company_id: int, branch_id: int | None) -> Branch | None:
    if branch_id is None:
        return None
    branch = db.get(Branch, branch_id)
    if not branch or int(branch.company_id) != int(company_id):
        raise HTTPException(400, "Şube seçili işyerine ait değil.")
    return branch


def _subject_query(payload: PersonnelProfileInitialize):
    if payload.subject_type == "employee":
        return PersonnelProfile.employee_id == payload.subject_id
    return PersonnelProfile.professional_id == payload.subject_id


def initialize_personnel_profile(
    db: Session,
    *,
    user: User,
    payload: PersonnelProfileInitialize,
) -> tuple[PersonnelProfile, bool]:
    """Açık özne bağıyla profil oluşturur; mevcut profili idempotent döndürür."""

    require_profile_write_role(user)
    ensure_company_access(db, user, payload.company_id)
    company = _company_for_profile(db, payload.company_id)
    branch = _validate_branch(db, payload.company_id, payload.branch_id)

    employee_id: int | None = None
    professional_id: int | None = None
    resolved_branch_id = branch.id if branch else None

    if payload.subject_type == "employee":
        employee = db.get(Employee, payload.subject_id)
        if not employee or int(employee.company_id) != int(payload.company_id):
            raise HTTPException(404, "Personel seçili işyerinde bulunamadı.")
        employee_id = employee.id
        if employee.branch_id is not None:
            if resolved_branch_id is not None and int(resolved_branch_id) != int(employee.branch_id):
                raise HTTPException(409, "Personelin kayıtlı şubesi ile seçilen şube uyuşmuyor.")
            resolved_branch_id = int(employee.branch_id)
            _validate_branch(db, payload.company_id, resolved_branch_id)
    else:
        professional = db.get(IsgProfessional, payload.subject_id)
        if not professional:
            raise HTTPException(404, "Profesyonel bulunamadı.")
        if int(professional.osgb_id) != int(company.osgb_id):
            raise HTTPException(403, "Profesyonel seçili işyerinin OSGB kapsamına ait değil.")
        active_assignment = db.scalar(
            select(WorkplaceAssignment.id)
            .where(
                WorkplaceAssignment.company_id == payload.company_id,
                WorkplaceAssignment.professional_id == professional.id,
                WorkplaceAssignment.osgb_id == professional.osgb_id,
                WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            )
            .limit(1)
        )
        if active_assignment is None:
            raise HTTPException(
                409,
                "Profesyonelin seçili işyerinde aktif görevlendirmesi yok.",
            )
        professional_id = professional.id

    existing = db.scalar(
        select(PersonnelProfile)
        .where(
            PersonnelProfile.company_id == payload.company_id,
            _subject_query(payload),
        )
        .limit(1)
    )
    if existing:
        if existing.status == "archived":
            raise HTTPException(
                409,
                "Bu özneye ait profil arşivlenmiştir; tarihsel profil yerinde yeniden aktifleştirilemez.",
            )
        return existing, False

    # Migration 0083 moves professional cards to OSGB scope.  Keep the
    # selected workplace only as a historical link and leave the live tenant
    # column empty; pre-0083 schemas retain the legacy company-scoped shape.
    osgb_professional_scope = bool(
        payload.subject_type == "professional"
        and "legacy_company_id" in PersonnelProfile.__table__.c
        and PersonnelProfile.__table__.c.company_id.nullable
    )
    profile = PersonnelProfile(
        osgb_id=int(company.osgb_id),
        company_id=None if osgb_professional_scope else payload.company_id,
        legacy_company_id=payload.company_id if osgb_professional_scope else None,
        branch_id=resolved_branch_id,
        subject_type=payload.subject_type,
        employee_id=employee_id,
        professional_id=professional_id,
        user_id=None,
        status="active",
        created_by_id=user.id,
    )
    db.add(profile)
    db.flush()
    add_audit_log(
        db,
        user=user,
        action="personnel_profile_initialized",
        entity_type="personnel_profile",
        entity_id=str(profile.id),
        module="personnel_profile",
        description=(
            f"Salt normal-profesyonel veri profili oluşturuldu; "
            f"company_id={profile.company_id}, subject_type={profile.subject_type}."
        ),
    )
    return profile, True


def get_profile_or_404(db: Session, profile_id: int) -> PersonnelProfile:
    profile = db.get(PersonnelProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Personel profili bulunamadı.")
    return profile


def archive_personnel_profile(
    db: Session,
    *,
    user: User,
    profile: PersonnelProfile,
) -> PersonnelProfile:
    require_profile_write_role(user)
    ensure_company_access(db, user, profile.company_id)
    if profile.status == "archived":
        return profile
    profile.status = "archived"
    profile.archived_by_id = user.id
    profile.archived_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action="personnel_profile_archived",
        entity_type="personnel_profile",
        entity_id=str(profile.id),
        module="personnel_profile",
        description="Personel profili arşivlendi; özne ve tarihsel sürümler korunur.",
    )
    return profile


def _latest_version(
    db: Session,
    model: type[VersionModel],
    *,
    profile_id: int,
    entry_key: str,
) -> VersionModel | None:
    return db.scalar(
        select(model)
        .where(model.profile_id == profile_id, model.entry_key == entry_key)
        .order_by(model.version.desc())
        .limit(1)
    )


def _new_entry_identity(
    db: Session,
    model: type[VersionModel],
    *,
    profile_id: int,
    requested_entry_key: str | None,
) -> tuple[str, int, int | None, VersionModel | None]:
    if not requested_entry_key:
        return str(uuid4()), 1, None, None
    latest = _latest_version(
        db,
        model,
        profile_id=profile_id,
        entry_key=requested_entry_key,
    )
    if not latest:
        raise HTTPException(
            404,
            "Sürümlenecek profil kaydı bulunamadı; yeni kayıt için entry_key göndermeyin.",
        )
    return requested_entry_key, int(latest.version) + 1, latest.id, latest


def _same_values(latest: Any, values: dict[str, Any]) -> bool:
    return all(getattr(latest, key, None) == value for key, value in values.items())


def _profile_for_write(db: Session, user: User, profile_id: int) -> PersonnelProfile:
    require_profile_write_role(user)
    profile = get_profile_or_404(db, profile_id)
    ensure_company_access(db, user, profile.company_id)
    if profile.status != "active":
        raise HTTPException(409, "Arşivlenmiş profile yeni sürüm eklenemez.")
    return profile


def append_contact_version(
    db: Session,
    *,
    user: User,
    profile_id: int,
    payload: PersonnelContactVersionCreate,
) -> tuple[PersonnelProfileContact, bool]:
    profile = _profile_for_write(db, user, profile_id)
    entry_key, version, supersedes_id, latest = _new_entry_identity(
        db,
        PersonnelProfileContact,
        profile_id=profile.id,
        requested_entry_key=payload.entry_key,
    )
    values = {
        "contact_type": payload.contact_type,
        "label": payload.label,
        "contact_value": payload.contact_value,
        "is_primary": payload.is_primary,
        "visibility": payload.visibility,
        "verification_status": "unverified",
        "lifecycle_status": "active",
    }
    if latest:
        if latest.contact_type != payload.contact_type:
            raise HTTPException(409, "İletişim türü yerinde değiştirilemez; yeni kayıt oluşturun.")
        if _same_values(latest, values):
            return latest, False
    row = PersonnelProfileContact(
        profile_id=profile.id,
        company_id=profile.company_id,
        entry_key=entry_key,
        version=version,
        supersedes_id=supersedes_id,
        change_reason=payload.change_reason,
        created_by_id=user.id,
        **values,
    )
    db.add(row)
    db.flush()
    add_audit_log(
        db,
        user=user,
        action="personnel_profile_contact_version_added",
        entity_type="personnel_profile_contact",
        entity_id=str(row.id),
        module="personnel_profile",
        description=f"İletişim meta sürümü eklendi; profile_id={profile.id}, version={version}.",
    )
    return row, True


def append_competency_version(
    db: Session,
    *,
    user: User,
    profile_id: int,
    payload: PersonnelCompetencyVersionCreate,
) -> tuple[PersonnelProfileCompetency, bool]:
    profile = _profile_for_write(db, user, profile_id)
    entry_key, version, supersedes_id, latest = _new_entry_identity(
        db,
        PersonnelProfileCompetency,
        profile_id=profile.id,
        requested_entry_key=payload.entry_key,
    )
    values = {
        "category": payload.category,
        "name": payload.name,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "certificate_number": payload.certificate_number,
        "issuing_organization": payload.issuing_organization,
        "description": payload.description,
        "verification_status": "unverified",
        "lifecycle_status": "active",
    }
    if latest:
        if latest.category != payload.category:
            raise HTTPException(409, "Yeterlilik kategorisi yerinde değiştirilemez; yeni kayıt oluşturun.")
        if _same_values(latest, values):
            return latest, False
    row = PersonnelProfileCompetency(
        profile_id=profile.id,
        company_id=profile.company_id,
        entry_key=entry_key,
        version=version,
        supersedes_id=supersedes_id,
        change_reason=payload.change_reason,
        created_by_id=user.id,
        **values,
    )
    db.add(row)
    db.flush()
    add_audit_log(
        db,
        user=user,
        action="personnel_profile_competency_version_added",
        entity_type="personnel_profile_competency",
        entity_id=str(row.id),
        module="personnel_profile",
        description=f"Yeterlilik sürümü eklendi; profile_id={profile.id}, version={version}.",
    )
    return row, True


def append_experience_version(
    db: Session,
    *,
    user: User,
    profile_id: int,
    payload: PersonnelExperienceVersionCreate,
) -> tuple[PersonnelProfileExperience, bool]:
    profile = _profile_for_write(db, user, profile_id)
    entry_key, version, supersedes_id, latest = _new_entry_identity(
        db,
        PersonnelProfileExperience,
        profile_id=profile.id,
        requested_entry_key=payload.entry_key,
    )
    values = {
        "organization_name": payload.organization_name,
        "position": payload.position,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "employment_type": payload.employment_type,
        "sector": payload.sector,
        "nace_activity": payload.nace_activity,
        "project_name": payload.project_name,
        "professional_summary": payload.professional_summary,
        "responsibilities": payload.responsibilities,
        "visibility": payload.visibility,
        "lifecycle_status": "active",
    }
    if latest and _same_values(latest, values):
        return latest, False
    row = PersonnelProfileExperience(
        profile_id=profile.id,
        company_id=profile.company_id,
        entry_key=entry_key,
        version=version,
        supersedes_id=supersedes_id,
        change_reason=payload.change_reason,
        created_by_id=user.id,
        **values,
    )
    db.add(row)
    db.flush()
    add_audit_log(
        db,
        user=user,
        action="personnel_profile_experience_version_added",
        entity_type="personnel_profile_experience",
        entity_id=str(row.id),
        module="personnel_profile",
        description=f"Deneyim özeti sürümü eklendi; profile_id={profile.id}, version={version}.",
    )
    return row, True


def _latest_rows(rows: Iterable[VersionModel]) -> list[VersionModel]:
    latest: dict[str, VersionModel] = {}
    for row in rows:
        current = latest.get(row.entry_key)
        if current is None or int(row.version) > int(current.version):
            latest[row.entry_key] = row
    return sorted(latest.values(), key=lambda row: (row.created_at, row.id))


def profile_snapshot(db: Session, profile: PersonnelProfile) -> dict[str, Any]:
    """Son sürümleri döndürür; geçmiş satırları değiştirmez veya silmez."""

    contacts = _latest_rows(
        db.scalars(
            select(PersonnelProfileContact).where(
                PersonnelProfileContact.profile_id == profile.id
            )
        ).all()
    )
    competencies = _latest_rows(
        db.scalars(
            select(PersonnelProfileCompetency).where(
                PersonnelProfileCompetency.profile_id == profile.id
            )
        ).all()
    )
    experiences = _latest_rows(
        db.scalars(
            select(PersonnelProfileExperience).where(
                PersonnelProfileExperience.profile_id == profile.id
            )
        ).all()
    )

    return {
        "profile": {
            "id": profile.id,
            "osgb_id": profile.osgb_id,
            "company_id": profile.company_id,
            "branch_id": profile.branch_id,
            "subject_type": profile.subject_type,
            "employee_id": profile.employee_id,
            "professional_id": profile.professional_id,
            "user_id": profile.user_id,
            "status": profile.status,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "archived_at": profile.archived_at.isoformat() if profile.archived_at else None,
        },
        "contacts": [
            {
                "id": row.id,
                "entry_key": row.entry_key,
                "version": row.version,
                "contact_type": row.contact_type,
                "label": row.label,
                "contact_value": row.contact_value,
                "is_primary": row.is_primary,
                "visibility": row.visibility,
                "verification_status": row.verification_status,
                "lifecycle_status": row.lifecycle_status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in contacts
        ],
        "competencies": [
            {
                "id": row.id,
                "entry_key": row.entry_key,
                "version": row.version,
                "category": row.category,
                "name": row.name,
                "start_date": row.start_date.isoformat() if row.start_date else None,
                "end_date": row.end_date.isoformat() if row.end_date else None,
                "certificate_number": row.certificate_number,
                "issuing_organization": row.issuing_organization,
                "description": row.description,
                "verification_status": row.verification_status,
                "lifecycle_status": row.lifecycle_status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in competencies
        ],
        "experiences": [
            {
                "id": row.id,
                "entry_key": row.entry_key,
                "version": row.version,
                "organization_name": row.organization_name,
                "position": row.position,
                "start_date": row.start_date.isoformat() if row.start_date else None,
                "end_date": row.end_date.isoformat() if row.end_date else None,
                "employment_type": row.employment_type,
                "sector": row.sector,
                "nace_activity": row.nace_activity,
                "project_name": row.project_name,
                "professional_summary": row.professional_summary,
                "responsibilities": row.responsibilities,
                "visibility": row.visibility,
                "lifecycle_status": row.lifecycle_status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in experiences
        ],
        "privacy": {
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
        },
    }
