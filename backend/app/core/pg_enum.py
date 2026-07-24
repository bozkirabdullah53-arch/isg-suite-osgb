"""Postgres enum ADD VALUE — savepoint ile güvenli (transaction abort önleme)."""
from __future__ import annotations

from sqlalchemy import text


def pg_add_enum_value(bind, enum_name: str, value: str) -> None:
    """Enum yoksa veya değer varsa no-op; hata savepoint içinde kalır."""
    if bind.dialect.name != "postgresql":
        return
    exists = bind.execute(
        text("SELECT 1 FROM pg_type WHERE typname = :n"),
        {"n": enum_name},
    ).scalar()
    if not exists:
        return
    has = bind.execute(
        text(
            "SELECT 1 FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid "
            "WHERE t.typname = :n AND e.enumlabel = :v"
        ),
        {"n": enum_name, "v": value},
    ).scalar()
    if has:
        return
    with bind.begin_nested():
        bind.execute(text(f"ALTER TYPE {enum_name} ADD VALUE '{value}'"))
