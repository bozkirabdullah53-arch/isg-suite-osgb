"""Firma erişim kapsamı.

OSGB uzman / hekim / DSP yalnızca kendisine görevlendirilen işyerlerine erişir
(WorkplaceAssignment). Kullanıcı ↔ profesyonel eşlemesi e-posta (veya ad) ile yapılır.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentStatus,
    Company,
    IsgProfessional,
    ProfessionalType,
    User,
    UserRole,
    WorkplaceAssignment,
)

_OSGB_FIELD_ROLES = {
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
}

_ROLE_TO_PRO_TYPE = {
    UserRole.SAFETY_SPECIALIST: ProfessionalType.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN: ProfessionalType.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL: ProfessionalType.OTHER_HEALTH_PERSONNEL,
}


def find_professional_for_user(db: Session, user: User) -> IsgProfessional | None:
    """Kullanıcıyı İSG profesyoneli kaydıyla eşle (önce e-posta, sonra ad)."""
    if user.role not in _OSGB_FIELD_ROLES:
        return None
    ptype = _ROLE_TO_PRO_TYPE.get(user.role)
    stmt = select(IsgProfessional).where(IsgProfessional.is_active.is_(True))
    if user.osgb_id:
        stmt = stmt.where(IsgProfessional.osgb_id == user.osgb_id)
    if ptype:
        stmt = stmt.where(IsgProfessional.professional_type == ptype)

    email = (user.email or "").strip().casefold()
    if email:
        by_email = db.scalar(
            stmt.where(func.lower(IsgProfessional.email) == email).limit(1)
        )
        if by_email:
            return by_email

    name = (user.full_name or "").strip().casefold()
    if name:
        pros = list(db.scalars(stmt).all())
        for p in pros:
            if (p.full_name or "").strip().casefold() == name:
                return p
    return None


def assigned_company_ids(db: Session, user: User) -> list[int]:
    """Uzman/hekim/DSP için aktif görevlendirildiği işyeri id listesi."""
    if user.role == UserRole.GLOBAL_ADMIN:
        return []  # sınırsız — çağıran filtre kullanmaz
    if user.role == UserRole.COMPANY_ADMIN:
        return [user.company_id] if user.company_id else []

    if user.role in _OSGB_FIELD_ROLES:
        pro = find_professional_for_user(db, user)
        if pro:
            ids = list(
                db.scalars(
                    select(WorkplaceAssignment.company_id).where(
                        WorkplaceAssignment.professional_id == pro.id,
                        WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
                    )
                ).all()
            )
            # Tekrarları temizle, sırayı koru
            seen: set[int] = set()
            ordered: list[int] = []
            for i in ids:
                if i not in seen:
                    seen.add(i)
                    ordered.append(i)
            if ordered:
                return ordered
        # Görevlendirme yoksa eski tek-firma hesabı (company_id bağlı uzman)
        if user.company_id:
            return [user.company_id]
        return []

    if user.company_id:
        return [user.company_id]
    return []


def ensure_company_access(db: Session, user: User, company_id: int | None) -> int:
    """Kullanıcının firmaya erişimini doğrular; geçerli company_id döner."""
    if not company_id:
        raise HTTPException(422, "Firma seçilmelidir.")
    if user.role == UserRole.GLOBAL_ADMIN:
        if not db.get(Company, company_id):
            raise HTTPException(404, "Firma bulunamadı.")
        return company_id

    allowed = assigned_company_ids(db, user)
    if company_id in allowed:
        return company_id

    if user.role in _OSGB_FIELD_ROLES and not allowed:
        raise HTTPException(
            403,
            "Size atanmış işyeri yok. Önce Görevlendirmeler’den bu uzmana firma bağlanmalı "
            "veya İSG Profesyonelleri kaydınızın e-postası kullanıcı e-postası ile aynı olmalı.",
        )
    raise HTTPException(403, "Bu firmaya erişemezsiniz — yalnızca görevlendirildiğiniz işyerleri.")


def companies_query_for_user(db: Session, user: User):
    """select(Company) üzerine uygulanacak filtre. None = global (filtre yok)."""
    if user.role == UserRole.GLOBAL_ADMIN:
        return None
    ids = assigned_company_ids(db, user)
    if not ids:
        return Company.id == -1
    return Company.id.in_(ids)


def resolve_employee_company_id(db: Session, user: User, company_id: int | None) -> int | None:
    """
    Personel listesi firma kapsamı.
    Dönüş: belirli id | None (çoklu — assigned listesiyle filtrele) | -1 (boş).
    """
    if user.role == UserRole.GLOBAL_ADMIN:
        return company_id

    allowed = assigned_company_ids(db, user)
    if not allowed:
        return -1
    if company_id:
        ensure_company_access(db, user, company_id)
        return company_id
    if len(allowed) == 1:
        return allowed[0]
    return None  # çağıran allowed ile filtreler


def accessible_company_ids_or_empty(db: Session, user: User) -> list[int]:
    """Personel/eğitim listelerinde çoklu firma filtresi için."""
    if user.role == UserRole.GLOBAL_ADMIN:
        return []
    return assigned_company_ids(db, user)
