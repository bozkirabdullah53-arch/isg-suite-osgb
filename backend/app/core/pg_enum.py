"""Postgres enum ADD VALUE — savepoint ile güvenli (transaction abort önleme)."""
from __future__ import annotations

import re

from sqlalchemy import text


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value or ""):
        raise ValueError("Geçersiz PostgreSQL enum adı.")
    return f'"{value}"'


def _quote_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


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
        bind.execute(
            text(
                f"ALTER TYPE {_quote_identifier(enum_name)} "
                f"ADD VALUE {_quote_literal(value)}"
            )
        )
