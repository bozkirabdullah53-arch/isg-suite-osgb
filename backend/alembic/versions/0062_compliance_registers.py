"""6331 compliance registers: periyodik kontrol, acil plan, ortam ölçüm, İSG kurulu.

Revision ID: 0062
Revises: 0061
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: Union[str, None] = "0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "periodic_controls",
    "emergency_plans",
    "workplace_measurements",
    "ohs_committee_members",
    "ohs_committee_meetings",
    "document_approvals",
)


def _company_scope_expr(table: str) -> str:
    return f"""
                  COALESCE(current_setting('app.current_user_id', true), '') = ''
                  OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                  OR (
                    COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                    AND {table}.company_id = ANY (
                      string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                    )
                  )
    """


def _enable_company_rls(table: str, policy: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    scope = _company_scope_expr(table)
    op.execute(
        sa.text(
            f"""
            DO $policy$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = current_schema()
                  AND tablename = '{table}'
                  AND policyname = '{policy}'
              ) THEN
                CREATE POLICY {policy} ON {table}
                  FOR ALL
                  USING ({scope})
                  WITH CHECK ({scope});
              END IF;
            END
            $policy$;
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("periodic_controls"):
        op.create_table(
            "periodic_controls",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("category", sa.String(40), nullable=False),
            sa.Column("equipment_name", sa.String(220), nullable=False),
            sa.Column("location", sa.String(220), nullable=True),
            sa.Column("serial_no", sa.String(120), nullable=True),
            sa.Column("last_control_date", sa.Date(), nullable=True),
            sa.Column("next_due_date", sa.Date(), nullable=True),
            sa.Column("control_firm", sa.String(220), nullable=True),
            sa.Column("report_ref", sa.String(220), nullable=True),
            sa.Column("result", sa.String(40), nullable=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("document_records.id"), nullable=True),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_periodic_controls_company_id", "periodic_controls", ["company_id"])
        op.create_index("ix_periodic_controls_category", "periodic_controls", ["category"])
        op.create_index("ix_periodic_controls_next_due_date", "periodic_controls", ["next_due_date"])

    if not insp.has_table("emergency_plans"):
        op.create_table(
            "emergency_plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("revision_no", sa.String(30), nullable=False, server_default="00"),
            sa.Column("plan_date", sa.Date(), nullable=True),
            sa.Column("next_review_date", sa.Date(), nullable=True),
            sa.Column("assembly_areas", sa.String(1000), nullable=True),
            sa.Column("scenario_summary", sa.String(4000), nullable=True),
            sa.Column("kroki_file_name", sa.String(255), nullable=True),
            sa.Column("kroki_storage_path", sa.String(500), nullable=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("document_records.id"), nullable=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="Aktif"),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_emergency_plans_company_id", "emergency_plans", ["company_id"])

    if not insp.has_table("workplace_measurements"):
        op.create_table(
            "workplace_measurements",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("measurement_type", sa.String(40), nullable=False),
            sa.Column("location", sa.String(220), nullable=True),
            sa.Column("measured_at", sa.Date(), nullable=False),
            sa.Column("value", sa.String(80), nullable=True),
            sa.Column("unit", sa.String(40), nullable=True),
            sa.Column("limit_value", sa.String(80), nullable=True),
            sa.Column("lab_name", sa.String(220), nullable=True),
            sa.Column("report_ref", sa.String(220), nullable=True),
            sa.Column("next_due_date", sa.Date(), nullable=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("document_records.id"), nullable=True),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_workplace_measurements_company_id", "workplace_measurements", ["company_id"])
        op.create_index("ix_workplace_measurements_type", "workplace_measurements", ["measurement_type"])
        op.create_index("ix_workplace_measurements_next_due", "workplace_measurements", ["next_due_date"])

    if not insp.has_table("ohs_committee_members"):
        op.create_table(
            "ohs_committee_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("role_code", sa.String(40), nullable=False),
            sa.Column("full_name", sa.String(160), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.String(1000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_ohs_committee_members_company_id", "ohs_committee_members", ["company_id"])

    if not insp.has_table("ohs_committee_meetings"):
        op.create_table(
            "ohs_committee_meetings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("meeting_date", sa.Date(), nullable=False),
            sa.Column("agenda", sa.String(4000), nullable=True),
            sa.Column("decisions", sa.String(4000), nullable=True),
            sa.Column("attendees", sa.String(2000), nullable=True),
            sa.Column("next_meeting_date", sa.Date(), nullable=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("document_records.id"), nullable=True),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_ohs_committee_meetings_company_id", "ohs_committee_meetings", ["company_id"])

    if not insp.has_table("document_approvals"):
        op.create_table(
            "document_approvals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("document_title", sa.String(220), nullable=False),
            sa.Column("document_kind", sa.String(80), nullable=False, server_default="genel"),
            sa.Column("approver_name", sa.String(160), nullable=False),
            sa.Column("approver_role", sa.String(80), nullable=True),
            sa.Column("approved_at", sa.Date(), nullable=True),
            sa.Column("signature_note", sa.String(1000), nullable=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="Bekliyor"),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("document_records.id"), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_document_approvals_company_id", "document_approvals", ["company_id"])

    # Incident SGK process columns (additive)
    cols = {c["name"] for c in insp.get_columns("incident_events")} if insp.has_table("incident_events") else set()
    if "sgk_due_date" not in cols:
        op.add_column("incident_events", sa.Column("sgk_due_date", sa.Date(), nullable=True))
    if "sgk_notification_status" not in cols:
        op.add_column(
            "incident_events",
            sa.Column("sgk_notification_status", sa.String(40), nullable=True),
        )

    # RLS only on Postgres
    try:
        dialect = bind.dialect.name
    except Exception:
        dialect = ""
    if dialect == "postgresql":
        for table in _TABLES:
            if insp.has_table(table):
                _enable_company_rls(table, f"{table}_tenant_isolation")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("incident_events"):
        cols = {c["name"] for c in insp.get_columns("incident_events")}
        if "sgk_notification_status" in cols:
            op.drop_column("incident_events", "sgk_notification_status")
        if "sgk_due_date" in cols:
            op.drop_column("incident_events", "sgk_due_date")
    for table in reversed(_TABLES):
        if insp.has_table(table):
            op.drop_table(table)
