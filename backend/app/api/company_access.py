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

_PRO_TYPE_TO_ROLE = {
    ProfessionalType.SAFETY_SPECIALIST: UserRole.SAFETY_SPECIALIST,
    ProfessionalType.WORKPLACE_PHYSICIAN: UserRole.WORKPLACE_PHYSICIAN,
    ProfessionalType.OTHER_HEALTH_PERSONNEL: UserRole.OTHER_HEALTH_PERSONNEL,
}


def _norm_text(value: str | None) -> str:
    s = (value or "").strip().casefold()
    for a, b in (("ı", "i"), ("İ", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c")):
        s = s.replace(a, b)
    return " ".join(s.split())


def find_professional_by_identity(db: Session, user: User) -> IsgProfessional | None:
    """E-posta (öncelik) veya ad ile aktif profesyonel; mümkünse kullanıcı OSGB’si ile sınırlı."""
    stmt = select(IsgProfessional).where(IsgProfessional.is_active.is_(True))
    if user.osgb_id:
        stmt = stmt.where(IsgProfessional.osgb_id == user.osgb_id)

    email = (user.email or "").strip().casefold()
    if email:
        by_email = db.scalar(
            stmt.where(func.lower(IsgProfessional.email) == email).order_by(IsgProfessional.id).limit(1)
        )
        if by_email:
            return by_email
        if user.osgb_id:
            return None

    name = _norm_text(user.full_name)
    if not name:
        return None
    # osgb_id yokken isimle eşleme — çapraz OSGB riski; yalnızca e-posta kabul
    if not user.osgb_id:
        return None
    matches = [p for p in db.scalars(stmt.order_by(IsgProfessional.id)).all() if _norm_text(p.full_name) == name]
    if len(matches) == 1:
        return matches[0]
    return None


def sync_user_from_professional(db: Session, user: User, *, commit: bool = False) -> User:
    """İSG profesyoneli kaydı varsa kullanıcı rolünü (hekim/uzman/DSP) ve OSGB’yi eşle.

    Global / firma yöneticisine dokunulmaz. Salt okunur veya yanlış saha rolü düzeltilir.
    """
    if user.role in (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN):
        return user

    pro = find_professional_by_identity(db, user)
    if not pro and user.role in _OSGB_FIELD_ROLES:
        pro = find_professional_for_user(db, user)
    if not pro:
        return user

    desired = _PRO_TYPE_TO_ROLE.get(pro.professional_type)
    changed = False
    if desired and user.role != desired:
        user.role = desired
        changed = True
    if pro.osgb_id and user.osgb_id != pro.osgb_id:
        user.osgb_id = pro.osgb_id
        changed = True
    if changed and commit:
        db.commit()
        db.refresh(user)
    return user


def link_user_to_professional(db: Session, professional: IsgProfessional) -> User | None:
    """Profesyonel e-posta veya ad ile kullanıcıyı bulup saha rolünü eşle."""
    if not professional or not professional.is_active:
        return None
    user = None
    email = (professional.email or "").strip().casefold()
    if email:
        user = db.scalar(select(User).where(func.lower(User.email) == email).limit(1))
    if not user:
        pname = _norm_text(professional.full_name)
        if pname and professional.osgb_id:
            cand_stmt = select(User).where(
                User.is_active.is_(True),
                User.osgb_id == professional.osgb_id,
            )
            for u in db.scalars(cand_stmt).all():
                if u.role in (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN):
                    continue
                if _norm_text(u.full_name) == pname:
                    user = u
                    break
    if not user or not user.is_active:
        return None
    if user.role in (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN):
        return user
    desired = _PRO_TYPE_TO_ROLE.get(professional.professional_type)
    if desired:
        user.role = desired
    if professional.osgb_id:
        user.osgb_id = professional.osgb_id
    return user


def sync_all_assigned_field_roles(db: Session, osgb_id: int | None = None) -> dict:
    """Aktif görevlendirmedeki uzman/hekim/DSP kullanıcı rollerini düzelt."""
    stmt = (
        select(IsgProfessional)
        .join(WorkplaceAssignment, WorkplaceAssignment.professional_id == IsgProfessional.id)
        .where(
            WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            IsgProfessional.is_active.is_(True),
        )
    )
    if osgb_id is not None:
        stmt = stmt.where(IsgProfessional.osgb_id == osgb_id)
    pros = list(db.scalars(stmt).all())
    seen: set[int] = set()
    linked = 0
    for pro in pros:
        if pro.id in seen:
            continue
        seen.add(pro.id)
        if link_user_to_professional(db, pro):
            linked += 1
    db.commit()
    return {"professionals": len(seen), "users_linked": linked, "osgb_id": osgb_id}


def find_professional_for_user(db: Session, user: User) -> IsgProfessional | None:
    """Kullanıcıyı İSG profesyoneli kaydıyla eşle (önce e-posta, sonra ad)."""
    if user.role not in _OSGB_FIELD_ROLES:
        return find_professional_by_identity(db, user)
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

    name = _norm_text(user.full_name)
    if name:
        pros = list(db.scalars(stmt).all())
        for p in pros:
            if _norm_text(p.full_name) == name:
                return p
    return find_professional_by_identity(db, user)


def assigned_company_ids(db: Session, user: User) -> list[int]:
    """Uzman/hekim/DSP için aktif görevlendirildiği işyeri id listesi."""
    if user.role == UserRole.GLOBAL_ADMIN:
        return []  # sınırsız — çağıran filtre kullanmaz
    if user.role == UserRole.COMPANY_ADMIN:
        if user.company_id:
            base = [user.company_id]
        elif user.osgb_id:
            base = list(
                db.scalars(select(Company.id).where(Company.osgb_id == user.osgb_id)).all()
            )
        else:
            base = []
        return _merge_membership_companies(db, user, base)

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
                return _merge_membership_companies(db, user, ordered)
        # Görevlendirme yoksa eski tek-firma hesabı (company_id bağlı uzman)
        if user.company_id:
            return _merge_membership_companies(db, user, [user.company_id])
        return _merge_membership_companies(db, user, [])

    if user.company_id:
        return _merge_membership_companies(db, user, [user.company_id])
    return _merge_membership_companies(db, user, [])


def _merge_membership_companies(db: Session, user: User, base: list[int]) -> list[int]:
    """P1-04: WorkplaceMembership satırları erişimi genişletir (daraltmaz)."""
    try:
        from app.models.entities import WorkplaceMembership

        extra = list(
            db.scalars(
                select(WorkplaceMembership.company_id).where(
                    WorkplaceMembership.user_id == user.id,
                    WorkplaceMembership.is_active.is_(True),
                )
            ).all()
        )
    except Exception:
        return base
    if not extra:
        return base
    seen = set(base)
    out = list(base)
    for cid in extra:
        if cid is None:
            continue
        i = int(cid)
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


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
        # P1-03b: TenantContext varsa OSGB çapraz erişimini ikinci kez kes
        company = db.get(Company, company_id)
        osgb = getattr(company, "osgb_id", None) if company is not None else None
        if isinstance(osgb, int):
            from app.core.tenant_context import assert_osgb_access, current_tenant

            ctx = current_tenant()
            if ctx is not None and not ctx.is_global and isinstance(ctx.osgb_id, int):
                assert_osgb_access(osgb)
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


def effective_company_id(db: Session, user: User, company_id: int | None = None) -> int:
    """
    Tek firma gerektiren endpointler için.
    - global_admin: company_id zorunlu
    - diğerleri: atanan firmalar; company_id yoksa tek atama varsa onu kullan
    """
    if user.role == UserRole.GLOBAL_ADMIN:
        if not company_id:
            raise HTTPException(422, "Global yönetici için company_id zorunludur.")
        if not db.get(Company, company_id):
            raise HTTPException(404, "Firma bulunamadı.")
        return company_id

    allowed = assigned_company_ids(db, user)
    if not allowed:
        raise HTTPException(
            403,
            "Size atanmış işyeri yok. Görevlendirmeler’den firma bağlanmalı.",
        )
    if company_id:
        if company_id not in allowed:
            raise HTTPException(403, "Bu firmaya erişemezsiniz — yalnızca görevlendirildiğiniz işyerleri.")
        return company_id
    if len(allowed) == 1:
        return allowed[0]
    raise HTTPException(422, "Birden fazla işyeriniz var; company_id seçin.")


def company_ids_for_query(db: Session, user: User, company_id: int | None = None) -> list[int] | None:
    """
    Liste filtreleri için.
    - None dönünce: global admin, tüm firmalar (filtre yok)
    - [] : erişim yok
    - [ids...] : IN filtresi
    """
    if user.role == UserRole.GLOBAL_ADMIN:
        if company_id:
            return [company_id]
        return None
    allowed = assigned_company_ids(db, user)
    if not allowed:
        return []
    if company_id:
        ensure_company_access(db, user, company_id)
        return [company_id]
    return allowed
