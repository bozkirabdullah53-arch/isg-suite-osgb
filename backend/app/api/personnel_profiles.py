"""Dijital Personel Kartı Faz 2 — salt okunur, migration içermeyen API.

Mevcut personel/profesyonel endpointlerini değiştirmez. Feature kapalıyken yalnız
readiness teşhisi kullanılabilir; profil özetleri fail-closed biçimde reddedilir.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
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
        if not user.osgb_id or int(user.osgb_id) != int(professional.osgb_id):
            raise HTTPException(403, "Bu profesyonel profilini görüntüleyemezsiniz.")
        return
    if user.role in _FIELD_ROLES:
        own = find_professional_for_user(db, user)
        if not own or int(own.id) != int(professional.id):
            raise HTTPException(403, "Yalnızca kendi profesyonel profilinizi görüntüleyebilirsiniz.")
        return
    raise HTTPException(403, "Bu profesyonel profilini görüntüleme yetkiniz yok.")


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
