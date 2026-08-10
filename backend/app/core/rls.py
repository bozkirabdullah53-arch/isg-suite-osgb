"""PostgreSQL RLS oturum değişkeni (P1-03).

Vars:
- app.current_user_id — boşsa (migrasyon/job) RLS geçiş
- app.rls_admin — memberships vb. (global/OSGB admin)
- app.rls_bypass — global admin: tüm satırlar; ayrıca allowed_company_ids
  hesabında geçici (chicken-egg önleme)
- app.allowed_company_ids — CSV firma id (doküman/sağlık RLS)
- app.current_company_id / app.current_osgb_id — yardımcı bağlam
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

    # Memberships: global / OSGB admin kendi satırları dışında yönetim
    admin = "1" if user.role in (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN) else ""
    _set(db, "app.rls_admin", admin)
    health_clinical = "1" if user.role in (
        UserRole.WORKPLACE_PHYSICIAN,
        UserRole.OTHER_HEALTH_PERSONNEL,
    ) else ""
    _set(db, "app.health_clinical_access", health_clinical)

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
