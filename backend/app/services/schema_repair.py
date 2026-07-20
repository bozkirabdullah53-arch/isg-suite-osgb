"""Şema onarımı — eksik migration kolon/tablolarını idempotent tamamlar."""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.core.database import engine


def _columns(table: str) -> set[str]:
    insp = inspect(engine)
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _tables() -> set[str]:
    return set(inspect(engine).get_table_names())


def repair_schema() -> None:
    dialect = engine.dialect.name
    tables = _tables()

    if "osgb_applications" in tables:
        cols = _columns("osgb_applications")
        stmts: list[str] = []
        if "contract_accepted" not in cols:
            stmts.append(
                "ALTER TABLE osgb_applications ADD COLUMN contract_accepted BOOLEAN NOT NULL DEFAULT false"
                if dialect != "sqlite"
                else "ALTER TABLE osgb_applications ADD COLUMN contract_accepted BOOLEAN NOT NULL DEFAULT 0"
            )
        if "personal_data_accepted" not in cols:
            stmts.append(
                "ALTER TABLE osgb_applications ADD COLUMN personal_data_accepted BOOLEAN NOT NULL DEFAULT false"
                if dialect != "sqlite"
                else "ALTER TABLE osgb_applications ADD COLUMN personal_data_accepted BOOLEAN NOT NULL DEFAULT 0"
            )
        with engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))

    if "osgb_organizations" in tables:
        cols = _columns("osgb_organizations")
        if "archived_at" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE osgb_organizations ADD COLUMN archived_at TIMESTAMP NULL"))

    # Eksik EİSA tabloları için create_all yedekleri start.sh'de; burada yalnızca kritik kolonlar.
