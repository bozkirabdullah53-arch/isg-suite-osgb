"""PostgreSQL RLS oturum değişkeni (P1-03).

Vars:
- app.current_user_id — boşsa (migrasyon/job) RLS geçiş
- app.rls_admin — memberships vb. (global/OSGB admin)
- app.rls_bypass — global admin: tüm satırlar
- app.allowed_company_ids — CSV firma id (doküman/sağlık RLS)
- app.current_company_id / app.current_osgb_id — yardımcı bağlam
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entities import User, UserRole


def _set(db: Session, key: str, value: str) -> None:
    db.execute(text("SELECT set_config(:k, :v, true)"), {"k": key, "v": value})


def _clear_tenant_vars(db: Session) -> None:
    _set(db, "app.current_user_id", "")
    _set(db, "app.rls_admin", "")
    _set(db, "app.rls_bypass", "")
    _set(db, "app.allowed_company_ids", "")
    _set(db, "app.current_company_id", "")
    _set(db, "app.current_osgb_id", "")


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

    if user.role == UserRole.GLOBAL_ADMIN:
        _set(db, "app.rls_bypass", "1")
        _set(db, "app.allowed_company_ids", "")
        return

    _set(db, "app.rls_bypass", "")
    # Firma listesi — document_records / health_records politikası
    from app.api.company_access import assigned_company_ids

    ids = assigned_company_ids(db, user)
    _set(db, "app.allowed_company_ids", ",".join(str(int(i)) for i in ids) if ids else "")
