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

    if "eisa_error_reports" not in tables:
        from app.models.entities import EisaErrorReport  # noqa: F401

        EisaErrorReport.__table__.create(bind=engine, checkfirst=True)

    if "password_reset_tokens" not in tables:
        from app.models.entities import PasswordResetToken  # noqa: F401

        PasswordResetToken.__table__.create(bind=engine, checkfirst=True)

    if "users" in tables:
        cols = _columns("users")
        user_cols: list[tuple[str, str]] = [
            ("failed_login_count", "INTEGER NOT NULL DEFAULT 0" if dialect != "sqlite" else "INTEGER DEFAULT 0"),
            ("locked_until", "TIMESTAMP" if dialect != "sqlite" else "DATETIME"),
            ("mfa_enabled", "BOOLEAN NOT NULL DEFAULT false" if dialect != "sqlite" else "BOOLEAN DEFAULT 0"),
            ("mfa_secret_encrypted", "VARCHAR(500)"),
            ("mfa_recovery_hashes", "TEXT"),
        ]
        stmts = [
            f"ALTER TABLE users ADD COLUMN {name} {ctype}"
            for name, ctype in user_cols
            if name not in cols
        ]
        if stmts:
            with engine.begin() as conn:
                for stmt in stmts:
                    conn.execute(text(stmt))

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

    # health_records: PRO parity + rapor kolonları (0012/0015) — create_all eklemez
    if "health_records" in tables:
        cols = _columns("health_records")
        health_cols: list[tuple[str, str]] = [
            ("audiometry_date", "DATE"),
            ("audiometry_result", "VARCHAR(240)"),
            ("spirometry_date", "DATE"),
            ("spirometry_result", "VARCHAR(240)"),
            ("chest_xray_date", "DATE"),
            ("chest_xray_result", "VARCHAR(240)"),
            ("blood_lead_date", "DATE"),
            ("blood_lead_value", "DOUBLE PRECISION" if dialect == "postgresql" else "FLOAT"),
            ("blood_lead_unit", "VARCHAR(20)"),
            ("blood_lead_ref", "DOUBLE PRECISION" if dialect == "postgresql" else "FLOAT"),
            ("blood_lead_eval", "VARCHAR(40)"),
            ("suggested_tests", "VARCHAR(1000)"),
            ("exposures", "VARCHAR(1000)"),
            ("follow_up_note", "VARCHAR(1500)"),
            ("other_biological_test", "VARCHAR(1000)"),
            ("report_file_name", "VARCHAR(255)"),
            ("report_storage_path", "VARCHAR(500)"),
            ("report_content_type", "VARCHAR(120)"),
            ("deleted_at", "TIMESTAMP" if dialect != "sqlite" else "DATETIME"),
        ]
        stmts = [
            f"ALTER TABLE health_records ADD COLUMN {name} {ctype}"
            for name, ctype in health_cols
            if name not in cols
        ]
        if stmts:
            with engine.begin() as conn:
                for stmt in stmts:
                    conn.execute(text(stmt))

    # health enum: canlıda isim (FIT) / değer (fit) karışıklığı → varchar
    if dialect == "postgresql":
        for table, column, enum_type in (
            ("health_records", "record_type", "healthrecordtype"),
            ("health_records", "fitness_status", "healthfitnessstatus"),
        ):
            if table not in tables:
                continue
            with engine.begin() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT data_type, udt_name
                        FROM information_schema.columns
                        WHERE table_name = :t AND column_name = :c
                        """
                    ),
                    {"t": table, "c": column},
                ).first()
                if row and (row[0] == "USER-DEFINED" or (row[1] or "") == enum_type):
                    conn.execute(
                        text(
                            f"""
                            ALTER TABLE {table}
                            ALTER COLUMN {column} TYPE VARCHAR(40)
                            USING lower(replace({column}::text, ' ', '_'))
                            """
                        )
                    )
                    try:
                        conn.execute(text(f"DROP TYPE IF EXISTS {enum_type}"))
                    except Exception:
                        pass

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

    # 0.9.119 — SDS kimyasal ürün sicili
    if "chemical_products" not in tables:
        bool_false = "0" if dialect == "sqlite" else "false"
        bool_true = "1" if dialect == "sqlite" else "true"
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE chemical_products (
                        id INTEGER PRIMARY KEY {"AUTOINCREMENT" if dialect == "sqlite" else ""},
                        company_id INTEGER NOT NULL,
                        branch_id INTEGER,
                        product_name VARCHAR(220) NOT NULL,
                        cas_number VARCHAR(40),
                        has_sds_file BOOLEAN NOT NULL DEFAULT {bool_false},
                        document_id INTEGER,
                        next_review_date DATE,
                        notes VARCHAR(1000),
                        ghs_checklist_json VARCHAR(500),
                        is_active BOOLEAN NOT NULL DEFAULT {bool_true},
                        created_by_id INTEGER NOT NULL,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS ix_chemical_products_company_id ON chemical_products (company_id)",
                "CREATE INDEX IF NOT EXISTS ix_chemical_products_product_name ON chemical_products (product_name)",
                "CREATE INDEX IF NOT EXISTS ix_chemical_products_next_review_date ON chemical_products (next_review_date)",
                "CREATE INDEX IF NOT EXISTS ix_chemical_products_document_id ON chemical_products (document_id)",
            ):
                try:
                    conn.execute(text(idx_sql))
                except Exception:
                    pass

    # 0.9.120 — GHS checklist kolonu
    if "chemical_products" in _tables():
        cols = _columns("chemical_products")
        if "ghs_checklist_json" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE chemical_products ADD COLUMN ghs_checklist_json VARCHAR(500)")
                )

    # 0.9.121 — Risk medya tehlike etiketi checklist
    if "risk_media" in _tables():
        cols = _columns("risk_media")
        if "tags_json" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE risk_media ADD COLUMN tags_json VARCHAR(500)"))