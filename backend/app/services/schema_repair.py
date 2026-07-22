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

    # 0.9.131 — Tatbikat yönetimi tabloları (yalnızca eksikse oluştur)
    if "drill_records" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS drill_records (
                        id INTEGER PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES companies(id),
                        drill_type VARCHAR(80) NOT NULL,
                        drill_date DATE NOT NULL,
                        start_time VARCHAR(10),
                        end_time VARCHAR(10),
                        responsible VARCHAR(200),
                        participant_count INTEGER NOT NULL DEFAULT 0,
                        assembly_area VARCHAR(300),
                        status VARCHAR(20) NOT NULL DEFAULT 'planlandi',
                        scenario VARCHAR(10000) NOT NULL,
                        gaps VARCHAR(10000),
                        result VARCHAR(10000),
                        participants_json VARCHAR(8000),
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_by_id INTEGER NOT NULL REFERENCES users(id),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS ix_drill_records_company_id ON drill_records (company_id)",
                "CREATE INDEX IF NOT EXISTS ix_drill_records_drill_type ON drill_records (drill_type)",
                "CREATE INDEX IF NOT EXISTS ix_drill_records_drill_date ON drill_records (drill_date)",
                "CREATE INDEX IF NOT EXISTS ix_drill_records_status ON drill_records (status)",
                "CREATE INDEX IF NOT EXISTS ix_drill_records_is_active ON drill_records (is_active)",
            ):
                try:
                    conn.execute(text(idx_sql))
                except Exception:
                    pass
    if "drill_photos" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS drill_photos (
                        id INTEGER PRIMARY KEY,
                        drill_id INTEGER NOT NULL REFERENCES drill_records(id) ON DELETE CASCADE,
                        storage_path VARCHAR(500) NOT NULL,
                        original_name VARCHAR(255),
                        content_type VARCHAR(120),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_drill_photos_drill_id ON drill_photos (drill_id)"))
            except Exception:
                pass

    # 0.9.134 — Acil durum ekipleri tabloları (yalnızca eksikse oluştur)
    bool_false = "0" if dialect == "sqlite" else "false"
    bool_true = "1" if dialect == "sqlite" else "true"
    if "emergency_team_types" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS emergency_team_types (
                        id INTEGER PRIMARY KEY,
                        company_id INTEGER REFERENCES companies(id),
                        code VARCHAR(40) NOT NULL,
                        name VARCHAR(120) NOT NULL,
                        is_system BOOLEAN NOT NULL DEFAULT {bool_false},
                        min_members INTEGER NOT NULL DEFAULT 2,
                        is_active BOOLEAN NOT NULL DEFAULT {bool_true},
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_types_company_id ON emergency_team_types (company_id)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_types_code ON emergency_team_types (code)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_types_is_system ON emergency_team_types (is_system)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_types_is_active ON emergency_team_types (is_active)",
            ):
                try:
                    conn.execute(text(idx_sql))
                except Exception:
                    pass
    if "emergency_teams" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS emergency_teams (
                        id INTEGER PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES companies(id),
                        type_id INTEGER NOT NULL REFERENCES emergency_team_types(id),
                        name VARCHAR(160) NOT NULL,
                        leader_assignment_id INTEGER,
                        min_members INTEGER NOT NULL DEFAULT 2,
                        notes VARCHAR(2000),
                        is_active BOOLEAN NOT NULL DEFAULT {bool_true},
                        created_by_id INTEGER NOT NULL REFERENCES users(id),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS ix_emergency_teams_company_id ON emergency_teams (company_id)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_teams_type_id ON emergency_teams (type_id)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_teams_is_active ON emergency_teams (is_active)",
            ):
                try:
                    conn.execute(text(idx_sql))
                except Exception:
                    pass
    if "emergency_team_assignments" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS emergency_team_assignments (
                        id INTEGER PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES companies(id),
                        team_id INTEGER NOT NULL REFERENCES emergency_teams(id) ON DELETE CASCADE,
                        employee_id INTEGER NOT NULL REFERENCES employees(id),
                        membership VARCHAR(10) NOT NULL DEFAULT 'asil',
                        is_leader BOOLEAN NOT NULL DEFAULT {bool_false},
                        role_title VARCHAR(120),
                        shift VARCHAR(60),
                        phone VARCHAR(40),
                        email VARCHAR(255),
                        section VARCHAR(120),
                        personnel_no VARCHAR(60),
                        assign_start DATE,
                        assign_end DATE,
                        letter_date DATE,
                        letter_no VARCHAR(60),
                        assigned_by VARCHAR(160),
                        notes VARCHAR(2000),
                        is_active BOOLEAN NOT NULL DEFAULT {bool_true},
                        created_by_id INTEGER NOT NULL REFERENCES users(id),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_assignments_company_id ON emergency_team_assignments (company_id)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_assignments_team_id ON emergency_team_assignments (team_id)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_assignments_employee_id ON emergency_team_assignments (employee_id)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_assignments_membership ON emergency_team_assignments (membership)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_assignments_is_active ON emergency_team_assignments (is_active)",
            ):
                try:
                    conn.execute(text(idx_sql))
                except Exception:
                    pass
    if "emergency_team_trainings" not in _tables():
        float_type = "DOUBLE PRECISION" if dialect == "postgresql" else "FLOAT"
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS emergency_team_trainings (
                        id INTEGER PRIMARY KEY,
                        assignment_id INTEGER NOT NULL REFERENCES emergency_team_assignments(id) ON DELETE CASCADE,
                        training_type VARCHAR(120),
                        provider VARCHAR(160),
                        trainer VARCHAR(160),
                        training_date DATE,
                        duration_hours {float_type},
                        certificate_no VARCHAR(80),
                        valid_until DATE,
                        file_path VARCHAR(500),
                        first_aid_cert_no VARCHAR(80),
                        first_aid_center VARCHAR(160),
                        first_aid_start DATE,
                        first_aid_end DATE,
                        refresh_date DATE,
                        notes VARCHAR(2000),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_trainings_assignment_id ON emergency_team_trainings (assignment_id)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_team_trainings_valid_until ON emergency_team_trainings (valid_until)",
            ):
                try:
                    conn.execute(text(idx_sql))
                except Exception:
                    pass
    if "emergency_sufficiency_rules" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS emergency_sufficiency_rules (
                        id INTEGER PRIMARY KEY,
                        hazard_class VARCHAR(40),
                        team_code VARCHAR(40),
                        min_members INTEGER NOT NULL DEFAULT 2,
                        min_per_shift INTEGER NOT NULL DEFAULT 1,
                        notes VARCHAR(1000),
                        is_active BOOLEAN NOT NULL DEFAULT {bool_true}
                    )
                    """
                )
            )
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS ix_emergency_sufficiency_rules_hazard_class ON emergency_sufficiency_rules (hazard_class)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_sufficiency_rules_team_code ON emergency_sufficiency_rules (team_code)",
                "CREATE INDEX IF NOT EXISTS ix_emergency_sufficiency_rules_is_active ON emergency_sufficiency_rules (is_active)",
            ):
                try:
                    conn.execute(text(idx_sql))
                except Exception:
                    pass

    # 0.9.135 — Yıllık plan değerlendirme tabloları
    if "annual_plan_evaluations" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS annual_plan_evaluations (
                        id INTEGER PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES companies(id),
                        year INTEGER NOT NULL,
                        branch_id INTEGER REFERENCES branches(id),
                        report_status VARCHAR(40) NOT NULL DEFAULT 'hazirlaniyor',
                        report_date DATE,
                        specialist_name VARCHAR(160),
                        physician_name VARCHAR(160),
                        employer_name VARCHAR(160),
                        plan_item_count_at_start INTEGER NOT NULL DEFAULT 0,
                        notes VARCHAR(2000),
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_by_id INTEGER NOT NULL REFERENCES users(id),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
    if "annual_plan_evaluation_items" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS annual_plan_evaluation_items (
                        id INTEGER PRIMARY KEY,
                        evaluation_id INTEGER NOT NULL REFERENCES annual_plan_evaluations(id) ON DELETE CASCADE,
                        plan_item_id INTEGER NOT NULL UNIQUE REFERENCES annual_plan_items(id),
                        company_id INTEGER NOT NULL REFERENCES companies(id),
                        year INTEGER NOT NULL,
                        outcome_status VARCHAR(40) NOT NULL DEFAULT 'planlandi',
                        actual_start DATE,
                        actual_end DATE,
                        completion_pct INTEGER,
                        result_text VARCHAR(4000),
                        deviation_reason VARCHAR(2000),
                        delay_days INTEGER,
                        specialist_note VARCHAR(2000),
                        physician_note VARCHAR(2000),
                        employer_note VARCHAR(2000),
                        next_year_suggestion VARCHAR(2000),
                        target_met BOOLEAN,
                        capa_needed BOOLEAN NOT NULL DEFAULT 0,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
    if "annual_plan_eval_evidences" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS annual_plan_eval_evidences (
                        id INTEGER PRIMARY KEY,
                        evaluation_item_id INTEGER NOT NULL REFERENCES annual_plan_evaluation_items(id) ON DELETE CASCADE,
                        doc_type VARCHAR(80),
                        title VARCHAR(200),
                        doc_date DATE,
                        doc_no VARCHAR(80),
                        storage_path VARCHAR(500),
                        original_name VARCHAR(255),
                        content_type VARCHAR(120),
                        notes VARCHAR(1000),
                        uploaded_by_id INTEGER REFERENCES users(id),
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
    if "annual_plan_unplanned_activities" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS annual_plan_unplanned_activities (
                        id INTEGER PRIMARY KEY,
                        evaluation_id INTEGER NOT NULL REFERENCES annual_plan_evaluations(id) ON DELETE CASCADE,
                        company_id INTEGER NOT NULL REFERENCES companies(id),
                        year INTEGER NOT NULL,
                        activity VARCHAR(240) NOT NULL,
                        category VARCHAR(40),
                        done_date DATE,
                        reason VARCHAR(2000),
                        result_text VARCHAR(4000),
                        responsible_name VARCHAR(160),
                        suggest_next_year BOOLEAN NOT NULL DEFAULT 0,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_by_id INTEGER NOT NULL REFERENCES users(id),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
    if "annual_plan_eval_capas" not in _tables():
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS annual_plan_eval_capas (
                        id INTEGER PRIMARY KEY,
                        evaluation_id INTEGER NOT NULL REFERENCES annual_plan_evaluations(id) ON DELETE CASCADE,
                        evaluation_item_id INTEGER REFERENCES annual_plan_evaluation_items(id) ON DELETE SET NULL,
                        title VARCHAR(240) NOT NULL,
                        root_cause VARCHAR(2000),
                        action VARCHAR(2000),
                        responsible VARCHAR(160),
                        due_date DATE,
                        priority VARCHAR(40),
                        status VARCHAR(20) NOT NULL DEFAULT 'acik',
                        closed_at DATE,
                        notes VARCHAR(2000),
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_by_id INTEGER NOT NULL REFERENCES users(id),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

    # 0.9.140 — annual_plan_evaluations.verify_code
    if "annual_plan_evaluations" in _tables():
        cols = _columns("annual_plan_evaluations")
        if "verify_code" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE annual_plan_evaluations ADD COLUMN verify_code VARCHAR(40)"))
                try:
                    conn.execute(
                        text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS ix_annual_plan_evaluations_verify_code "
                            "ON annual_plan_evaluations (verify_code)"
                        )
                    )
                except Exception:
                    pass

