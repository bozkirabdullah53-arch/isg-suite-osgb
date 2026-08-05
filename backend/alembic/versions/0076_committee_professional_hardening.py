"""Professional OHS committee integrity and historical snapshot support.

Revision ID: 0076_committee_professional
Revises: 0075_rls_critical_expand
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0076_committee_professional"
down_revision: Union[str, None] = "0075_rls_critical_expand"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(insp, table: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("ohs_committee_members") or not insp.has_table("ohs_committee_meetings"):
        return

    member_cols = _columns(insp, "ohs_committee_members")
    additions = (
        ("employee_id", sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True)),
        ("user_id", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True)),
        ("branch_id", sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True)),
        ("identity_key", sa.Column("identity_key", sa.String(220), nullable=True)),
        ("source_type", sa.Column("source_type", sa.String(40), nullable=True)),
        ("source_ref", sa.Column("source_ref", sa.String(120), nullable=True)),
        ("job_title_snapshot", sa.Column("job_title_snapshot", sa.String(160), nullable=True)),
        ("professional_role_snapshot", sa.Column("professional_role_snapshot", sa.String(160), nullable=True)),
        ("email_snapshot", sa.Column("email_snapshot", sa.String(255), nullable=True)),
        ("is_mandatory", sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("false"))),
    )
    for name, column in additions:
        if name not in member_cols:
            op.add_column("ohs_committee_members", column)

    meeting_cols = _columns(insp, "ohs_committee_meetings")
    meeting_additions = (
        ("title", sa.Column("title", sa.String(220), nullable=True)),
        ("meeting_no", sa.Column("meeting_no", sa.String(60), nullable=True)),
        ("document_no", sa.Column("document_no", sa.String(80), nullable=True)),
        ("revision_no", sa.Column("revision_no", sa.String(30), nullable=False, server_default="00")),
        ("status", sa.Column("status", sa.String(40), nullable=False, server_default="draft")),
        ("signature_status", sa.Column("signature_status", sa.String(40), nullable=False, server_default="not_signed")),
        ("start_time", sa.Column("start_time", sa.String(10), nullable=True)),
        ("end_time", sa.Column("end_time", sa.String(10), nullable=True)),
        ("location", sa.Column("location", sa.String(220), nullable=True)),
        ("meeting_type", sa.Column("meeting_type", sa.String(60), nullable=True)),
        ("member_snapshot_json", sa.Column("member_snapshot_json", sa.Text(), nullable=True)),
        ("agenda_json", sa.Column("agenda_json", sa.Text(), nullable=True)),
        ("decisions_json", sa.Column("decisions_json", sa.Text(), nullable=True)),
        ("approval_reference", sa.Column("approval_reference", sa.String(160), nullable=True)),
        ("pdf_sha256", sa.Column("pdf_sha256", sa.String(64), nullable=True)),
        ("pdf_generated_at", sa.Column("pdf_generated_at", sa.DateTime(), nullable=True)),
    )
    for name, column in meeting_additions:
        if name not in meeting_cols:
            op.add_column("ohs_committee_meetings", column)

    if not insp.has_table("ohs_committee_duplicate_reports"):
        op.create_table(
            "ohs_committee_duplicate_reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("normalized_name", sa.String(180), nullable=False),
            sa.Column("member_ids", sa.String(1000), nullable=False),
            sa.Column("record_count", sa.Integer(), nullable=False),
            sa.Column("resolution_status", sa.String(40), nullable=False, server_default="review_required"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_ohs_committee_duplicate_reports_company", "ohs_committee_duplicate_reports", ["company_id"])

    # Historical duplicates are reported, never deleted or silently merged.
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("""
            INSERT INTO ohs_committee_duplicate_reports
                (company_id, normalized_name, member_ids, record_count, resolution_status)
            SELECT company_id, lower(trim(full_name)), string_agg(id::text, ',' ORDER BY id), count(*), 'review_required'
            FROM ohs_committee_members
            WHERE is_active = true
            GROUP BY company_id, lower(trim(full_name))
            HAVING count(*) > 1
            ON CONFLICT DO NOTHING
        """))
        op.execute(sa.text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ohs_committee_active_identity
            ON ohs_committee_members (company_id, identity_key)
            WHERE is_active = true AND identity_key IS NOT NULL
        """))
        op.execute(sa.text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ohs_committee_active_employee
            ON ohs_committee_members (company_id, employee_id)
            WHERE is_active = true AND employee_id IS NOT NULL
        """))
        op.execute(sa.text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ohs_committee_active_user
            ON ohs_committee_members (company_id, user_id)
            WHERE is_active = true AND user_id IS NOT NULL
        """))
    else:
        op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ohs_committee_active_identity ON ohs_committee_members(company_id, identity_key) WHERE is_active = 1 AND identity_key IS NOT NULL"))
        op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ohs_committee_active_employee ON ohs_committee_members(company_id, employee_id) WHERE is_active = 1 AND employee_id IS NOT NULL"))
        op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ohs_committee_active_user ON ohs_committee_members(company_id, user_id) WHERE is_active = 1 AND user_id IS NOT NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for index_name in (
        "uq_ohs_committee_active_user",
        "uq_ohs_committee_active_employee",
        "uq_ohs_committee_active_identity",
    ):
        try:
            op.drop_index(index_name, table_name="ohs_committee_members")
        except Exception:
            pass
    if insp.has_table("ohs_committee_duplicate_reports"):
        op.drop_table("ohs_committee_duplicate_reports")
    # Additive historical columns are intentionally retained on downgrade to avoid data loss.
