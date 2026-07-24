"""PostgreSQL RLS oturum değişkeni (P1-03 pilot).

SET LOCAL — istek transaction'ı bitince düşer.
SQLite / unset: no-op veya boş → policy tüm satırlara izin verir (migrasyon/job güvenli).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def apply_rls_user(db: Session, user_id: int | None) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    uid = "" if user_id is None else str(int(user_id))
    db.execute(text("SELECT set_config('app.current_user_id', :uid, true)"), {"uid": uid})
