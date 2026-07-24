"""PostgreSQL RLS oturum değişkeni (P1-03)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entities import User, UserRole


def apply_rls_user(db: Session, user: User | int | None) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    if user is None:
        db.execute(text("SELECT set_config('app.current_user_id', '', true)"))
        db.execute(text("SELECT set_config('app.rls_admin', '', true)"))
        return
    if isinstance(user, int):
        db.execute(text("SELECT set_config('app.current_user_id', :uid, true)"), {"uid": str(user)})
        db.execute(text("SELECT set_config('app.rls_admin', '', true)"))
        return
    db.execute(text("SELECT set_config('app.current_user_id', :uid, true)"), {"uid": str(int(user.id))})
    # Global / OSGB admin üyelik listelerini yönetebilir
    admin = "1" if user.role in (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN) else ""
    db.execute(text("SELECT set_config('app.rls_admin', :a, true)"), {"a": admin})
