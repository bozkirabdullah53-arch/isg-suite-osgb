from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.api.committee_professional import ROLE_LABELS, _member_rows


def test_member_rows_are_mutable_dicts_for_role_label_enrichment():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE ohs_committee_members (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                role_code TEXT NOT NULL,
                full_name TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                notes TEXT,
                employee_id INTEGER,
                user_id INTEGER,
                branch_id INTEGER,
                identity_key TEXT,
                source_type TEXT,
                source_ref TEXT,
                job_title_snapshot TEXT,
                professional_role_snapshot TEXT,
                email_snapshot TEXT,
                is_mandatory BOOLEAN NOT NULL,
                is_active BOOLEAN NOT NULL,
                created_at TEXT,
                removed_at TEXT,
                removed_by_id INTEGER,
                removal_reason_code TEXT,
                removal_reason_text TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO ohs_committee_members
                (id, company_id, role_code, full_name, is_mandatory, is_active)
            VALUES
                (1, 118, 'igu', 'Test Uzmanı', 1, 1)
        """))

    with Session(engine) as session:
        rows = _member_rows(session, 118)

    assert len(rows) == 1
    assert type(rows[0]) is dict
    rows[0]["role_label"] = ROLE_LABELS[rows[0]["role_code"]]
    assert rows[0]["role_label"] == "İş Güvenliği Uzmanı"
