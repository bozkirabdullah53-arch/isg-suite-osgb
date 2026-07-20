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
    if "eisa_archive_records" not in tables:
        from app.models.entities import EisaArchiveRecord  # noqa: F401

        EisaArchiveRecord.__table__.create(bind=engine, checkfirst=True)

    if "companies" in tables:
        cols = _columns("companies")
        stmts: list[str] = []
        if "address" not in cols:
            stmts.append("ALTER TABLE companies ADD COLUMN address VARCHAR(500)")
        if "phone" not in cols:
            stmts.append("ALTER TABLE companies ADD COLUMN phone VARCHAR(40)")
        if "authorized_person" not in cols:
            stmts.append("ALTER TABLE companies ADD COLUMN authorized_person VARCHAR(160)")
        if stmts:
            with engine.begin() as conn:
                for stmt in stmts:
                    conn.execute(text(stmt))

    # annual_plan_items.status: canlı Postgres enum etiketi (PLANNED) ≠ uygulama değeri (planned)
    if "annual_plan_items" in tables and dialect == "postgresql":
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_name = 'annual_plan_items' AND column_name = 'status'
                    """
                )
            ).first()
            if row:
                data_type, udt_name = row[0], (row[1] or "")
                if data_type == "USER-DEFINED" or udt_name == "annualplanstatus":
                    conn.execute(
                        text(
                            """
                            ALTER TABLE annual_plan_items
                            ALTER COLUMN status TYPE VARCHAR(40)
                            USING lower(status::text)
                            """
                        )
                    )
                    try:
                        conn.execute(text("DROP TYPE IF EXISTS annualplanstatus"))
                    except Exception:
                        pass
                else:
                    conn.execute(
                        text(
                            """
                            UPDATE annual_plan_items
                            SET status = lower(status)
                            WHERE status IS NOT NULL AND status <> lower(status)
                            """
                        )
                    )
