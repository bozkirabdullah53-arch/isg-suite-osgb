"""PostgreSQL RLS oturum değişkeni (P1-03).

Vars:
- app.current_user_id — boşsa (migrasyon/job) RLS geçiş
- app.rls_admin — memberships vb. (global/OSGB admin)
- app.rls_bypass — global admin: tüm satırlar; ayrıca allowed_company_ids
  hesabında geçici (chicken-egg önleme)
- app.allowed_company_ids — CSV firma id (doküman/sağlık RLS)
- app.current_company_id / app.current_osgb_id — yardımcı bağlam
- app.health_employer_access — normal işyeri yetkilisi için sağlık SELECT izni
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entities import User, UserRole


def _set(db: Session, key: str, value: str) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    db.execute(text("SELECT set_config(:k, :v, true)"), {"k": key, "v": value})


def set_rls_bypass(db: Session, enabled: bool = True) -> None:
    """Geçici RLS bypass (INSERT chicken-egg / kapsam hesabı)."""
    _set(db, "app.rls_bypass", "1" if enabled else "")


def _allowed_csv(ids: list[int] | None) -> str:
    """Boş CSV yazma — PG `string_to_array('','')::int[]` 500 üretir; sentinel -1 kullan."""
    if not ids:
        return "-1"
    return ",".join(str(int(i)) for i in ids)


def _clear_tenant_vars(db: Session) -> None:
    _set(db, "app.current_user_id", "")
    _set(db, "app.rls_admin", "")
    _set(db, "app.rls_bypass", "")
    _set(db, "app.allowed_company_ids", "-1")
    _set(db, "app.current_company_id", "")
    _set(db, "app.current_osgb_id", "")
    _set(db, "app.health_clinical_access", "")
    _set(db, "app.health_employer_access", "")


def _has_osgb_admin_rls_privilege(user: User) -> bool:
    """RLS yönetici bayrağı yalnız global ve işyerine bağlı olmayan OSGB adminindir."""
    return user.role == UserRole.GLOBAL_ADMIN or (
        user.role == UserRole.COMPANY_ADMIN and user.company_id is None
    )


def _has_workplace_health_read_privilege(user: User) -> bool:
    """Klinik olmayan sağlık takibini tek işyeri hesabına aç."""
    return (
        user.role == UserRole.COMPANY_ADMIN
        and bool(getattr(user, "company_id", None))
    )


def apply_rls_user(db: Session, user: User | int | None) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    if user is None:
        _clear_tenant_vars(db)
        return
    if isinstance(user, int):
        _clear_tenant_vars(db)
        _set(db, "app.current_user_id", str(user))
        return

    _set(db, "app.current_user_id", str(int(user.id)))
    _set(db, "app.current_company_id", str(int(user.company_id)) if user.company_id else "")
    _set(db, "app.current_osgb_id", str(int(user.osgb_id)) if user.osgb_id else "")

    # İşyeri hesabı OSGB geneli RLS yönetici bayrağını alamaz; kendi company_id'si
    # allowed_company_ids ile korunur.
    admin = "1" if _has_osgb_admin_rls_privilege(user) else ""
    _set(db, "app.rls_admin", admin)
    health_clinical = "1" if user.role in (
        UserRole.WORKPLACE_PHYSICIAN,
        UserRole.OTHER_HEALTH_PERSONNEL,
    ) else ""
    _set(db, "app.health_clinical_access", health_clinical)
    health_employer = "1" if _has_workplace_health_read_privilege(user) else ""
    _set(db, "app.health_employer_access", health_employer)

    if user.role == UserRole.GLOBAL_ADMIN:
        _set(db, "app.rls_bypass", "1")
        _set(db, "app.allowed_company_ids", "-1")
        return

    # Firma listesi (assigned_company_ids → workplace_assignments okur).
    # Geçici bypass: FORCE RLS + henüz boş allowed_company_ids chicken-egg'ini önler.
    from app.api.company_access import assigned_company_ids

    _set(db, "app.rls_bypass", "1")
    try:
        ids = assigned_company_ids(db, user)
    finally:
        _set(db, "app.rls_bypass", "")
    _set(db, "app.allowed_company_ids", _allowed_csv(ids))
