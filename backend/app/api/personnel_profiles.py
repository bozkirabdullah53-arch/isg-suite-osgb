"""Dijital Personel Kartı API.

Faz 2 salt okunur özetleri korunur. Faz 3, mevcut Employee/IsgProfessional/User
kayıtlarını değiştirmeden açık özne bağlantılı profil kökü ve normal profesyonel
bilgi sürümleri ekler. Restricted veri, dosya, CV veya dış paylaşım içermez.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access, find_professional_for_user
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.personnel_profile_config import (
    personnel_profile_card_active,
    personnel_profile_rollout,
)
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
from app.models.personnel_profile import PersonnelProfile
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
    get_profile_or_404,
    initialize_personnel_profile,
    profile_snapshot,
)
from app.services.personnel_profile_readonly import (
    build_employee_profile_summary,
    build_personnel_profile_readiness,
    build_professional_profile_summary,
)


router = APIRouter(prefix="/personnel-profiles", tags=["Dijital Personel Kartı"])
_FIELD_ROLES = {
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
}


def _require_profile_active(company_id: int) -> dict[str, bool]:
    rollout = personnel_profile_rollout(company_id)
    if not personnel_profile_card_active(company_id):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "personnel_profile_disabled",
                "message": (
                    "Dijital Personel Kartı bu işyeri için kapalıdır. "
                    "Mevcut personel işlemleri etkilenmeden devam eder."
                ),
                "rollout": rollout,
            },
        )
    return rollout


def _ensure_professional_access(
    db: Session,
    user: User,
    professional: IsgProfessional,
    company_id: int,
) -> None:
    """Profesyonel kartını seçili şirket ve gerçek backend rolüyle sınırlar."""

    ensure_company_access(db, user, company_id)

    assignment_id = db.scalar(
        select(WorkplaceAssignment.id)
        .where(
            WorkplaceAssignment.company_id == company_id,
            WorkplaceAssignment.professional_id == professional.id,
            WorkplaceAssignment.osgb_id == professional.osgb_id,
            WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
        )
        .limit(1)
    )
    if assignment_id is None:
        raise HTTPException(
            status_code=404,
            detail="Bu profesyonel için seçili işyerinde aktif görevlendirme bulunamadı.",
        )

    if user.role == UserRole.GLOBAL_ADMIN:
        return
    if user.role == UserRole.COMPANY_ADMIN:
        if user.osgb_id and int(user.osgb_id) != int(professional.osgb_id):
            raise HTTPException(403, "Bu profesyonel profilini görüntüleyemezsiniz.")
        return
    if user.role in _FIELD_ROLES:
        own = find_professional_for_user(db, user)
        if not own or int(own.id) != int(professional.id):
            raise HTTPException(403, "Yalnızca kendi profesyonel profilinizi görüntüleyebilirsiniz.")
        return
    raise HTTPException(403, "Bu profesyonel profilini görüntüleme yetkiniz yok.")


def _ensure_extended_profile_read_access(
    db: Session,
    user: User,
    profile: PersonnelProfile,
) -> None:
    ensure_company_access(db, user, profile.company_id)
    if user.role == UserRole.GLOBAL_ADMIN:
        return
    if user.role == UserRole.COMPANY_ADMIN:
        if user.osgb_id and int(user.osgb_id) != int(profile.osgb_id):
            raise HTTPException(403, "Bu personel profilini görüntüleyemezsiniz.")
        return
    if user.role in _FIELD_ROLES and profile.subject_type == "professional":
        own = find_professional_for_user(db, user)
        if own and profile.professional_id and int(own.id) == int(profile.professional_id):
            return
    raise HTTPException(
        403,
        "Genişletilmiş personel profili yalnız yetkili yönetici veya profil sahibi profesyonel tarafından görüntülenebilir.",
    )


def _commit_with_duplicate_retry(db: Session, operation):
    try:
        result = operation()
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        result = operation()
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.get("/readiness")
def personnel_profile_readiness(
    company_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Şirket kapsamlı, hassas veri içermeyen rollout ve hazırlık özeti."""

    ensure_company_access(db, user, company_id)
    rollout = personnel_profile_rollout(company_id)
    return build_personnel_profile_readiness(company_id=company_id, rollout=rollout)


@router.get("/employee/{employee_id}/summary")
def employee_profile_summary(
    employee_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """İşyeri çalışanının restricted veri içermeyen minimum profil özeti."""

    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(404, "Personel bulunamadı.")
    ensure_company_access(db, user, employee.company_id)
    rollout = _require_profile_active(employee.company_id)

    company = db.get(Company, employee.company_id)
    branch = db.get(Branch, employee.branch_id) if employee.branch_id is not None else None
    if branch is not None and int(branch.company_id) != int(employee.company_id):
        raise HTTPException(409, "Personel şube ilişkisi işyeri ile uyumlu değil.")

    return build_employee_profile_summary(
        employee,
        company_name=company.name if company else None,
        branch_name=branch.name if branch else None,
        rollout=rollout,
    )


@router.get("/professional/{professional_id}/summary")
def professional_profile_summary(
    professional_id: int,
    company_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Seçili işyerine aktif atanmış profesyonelin minimum profil özeti."""

    professional = db.get(IsgProfessional, professional_id)
    if not professional:
        raise HTTPException(404, "Profesyonel bulunamadı.")

    _ensure_professional_access(db, user, professional, company_id)
    rollout = _require_profile_active(company_id)
    company = db.get(Company, company_id)

    active_assignment_count = int(
        db.scalar(
            select(func.count())
            .select_from(WorkplaceAssignment)
            .where(
                WorkplaceAssignment.professional_id == professional.id,
                WorkplaceAssignment.osgb_id == professional.osgb_id,
                WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
        or 0
    )

    return build_professional_profile_summary(
        professional,
        company_id=company_id,
        company_name=company.name if company else None,
        active_assignment_count=active_assignment_count,
        rollout=rollout,
    )


@router.post("")
def initialize_profile(
    payload: PersonnelProfileInitialize,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mevcut bir özneye açık bağla, backfill yapmadan profil kökü oluşturur."""

    _require_profile_active(payload.company_id)

    def operation():
        return initialize_personnel_profile(db, user=user, payload=payload)

    profile, created = _commit_with_duplicate_retry(db, operation)
    db.refresh(profile)
    return {
        "created": created,
        "profile": profile_snapshot(db, profile)["profile"],
        "privacy": profile_snapshot(db, profile)["privacy"],
    }


@router.get("/{profile_id}")
def get_extended_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Yetkili tarihsel erişim; feature kapansa bile mevcut profil okunabilir."""

    profile = get_profile_or_404(db, profile_id)
    _ensure_extended_profile_read_access(db, user, profile)
    return profile_snapshot(db, profile)


@router.post("/{profile_id}/contacts")
def add_contact_version(
    profile_id: int,
    payload: PersonnelContactVersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_profile_or_404(db, profile_id)
    _require_profile_active(profile.company_id)

    def operation():
        return append_contact_version(
            db, user=user, profile_id=profile_id, payload=payload
        )

    row, created = _commit_with_duplicate_retry(db, operation)
    db.refresh(row)
    return {
        "created": created,
        "id": row.id,
        "entry_key": row.entry_key,
        "version": row.version,
        "verification_status": row.verification_status,
        "lifecycle_status": row.lifecycle_status,
    }


@router.post("/{profile_id}/competencies")
def add_competency_version(
    profile_id: int,
    payload: PersonnelCompetencyVersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_profile_or_404(db, profile_id)
    _require_profile_active(profile.company_id)

    def operation():
        return append_competency_version(
            db, user=user, profile_id=profile_id, payload=payload
        )

    row, created = _commit_with_duplicate_retry(db, operation)
    db.refresh(row)
    return {
        "created": created,
        "id": row.id,
        "entry_key": row.entry_key,
        "version": row.version,
        "verification_status": row.verification_status,
        "lifecycle_status": row.lifecycle_status,
    }


@router.post("/{profile_id}/experiences")
def add_experience_version(
    profile_id: int,
    payload: PersonnelExperienceVersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_profile_or_404(db, profile_id)
    _require_profile_active(profile.company_id)

    def operation():
        return append_experience_version(
            db, user=user, profile_id=profile_id, payload=payload
        )

    row, created = _commit_with_duplicate_retry(db, operation)
    db.refresh(row)
    return {
        "created": created,
        "id": row.id,
        "entry_key": row.entry_key,
        "version": row.version,
        "lifecycle_status": row.lifecycle_status,
    }


@router.post("/{profile_id}/archive")
def archive_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_profile_or_404(db, profile_id)
    _require_profile_active(profile.company_id)
    try:
        archive_personnel_profile(db, user=user, profile=profile)
        db.commit()
        db.refresh(profile)
    except Exception:
        db.rollback()
        raise
    return {
        "id": profile.id,
        "status": profile.status,
        "archived_at": profile.archived_at.isoformat() if profile.archived_at else None,
    }
