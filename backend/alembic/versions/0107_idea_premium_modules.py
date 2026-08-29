"""Add IDEA-only PTW, contractor, visitor and field-mobile tables.

Revision ID: 0107_idea_premium_modules
Revises: 0106_remote_catalog_links
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0107_idea_premium_modules"
down_revision: Union[str, None] = "0106_remote_catalog_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_if_missing(inspector, name: str, factory) -> None:
    if not inspector.has_table(name):
        factory()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def work_permits():
        op.create_table(
            "work_permits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("permit_no", sa.String(40), nullable=False),
            sa.Column("permit_type", sa.String(40), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("location", sa.String(300), nullable=False),
            sa.Column("valid_from", sa.DateTime(), nullable=False),
            sa.Column("valid_until", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
            sa.Column("opening_checked_at", sa.DateTime(), nullable=True),
            sa.Column("opening_checked_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column("closed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("cancellation_note", sa.Text(), nullable=True),
            sa.Column("risk_id", sa.Integer(), sa.ForeignKey("risk_assessments.id", ondelete="SET NULL"), nullable=True),
            sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incident_events.id", ondelete="SET NULL"), nullable=True),
            sa.Column("dof_id", sa.Integer(), sa.ForeignKey("risk_dofs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("field_inspection_id", sa.Integer(), sa.ForeignKey("field_inspections.id", ondelete="SET NULL"), nullable=True),
            sa.Column("contractor_id", sa.Integer(), nullable=True),
            sa.Column("client_reference", sa.String(100), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("company_id", "client_reference", name="uq_work_permit_company_client_reference"),
            sa.UniqueConstraint("permit_no", name="uq_work_permit_no"),
        )

    def work_permit_employees():
        op.create_table(
            "work_permit_employees",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("permit_id", sa.Integer(), sa.ForeignKey("work_permits.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("permit_id", "employee_id", name="uq_work_permit_employee"),
        )

    def work_permit_controls():
        op.create_table(
            "work_permit_controls",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("permit_id", sa.Integer(), sa.ForeignKey("work_permits.id", ondelete="CASCADE"), nullable=False),
            sa.Column("control_type", sa.String(50), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("measured_value", sa.String(80), nullable=True),
            sa.Column("unit", sa.String(30), nullable=True),
            sa.Column("checked_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("checked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("permit_id", "control_type", name="uq_work_permit_control_type"),
        )

    def work_permit_approvers():
        op.create_table(
            "work_permit_approvers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("permit_id", sa.Integer(), sa.ForeignKey("work_permits.id", ondelete="CASCADE"), nullable=False),
            sa.Column("approver_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("step_order", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("permit_id", "step_order", name="uq_work_permit_approver_step"),
        )

    def contractor_companies():
        op.create_table(
            "contractor_companies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(220), nullable=False),
            sa.Column("contract_number", sa.String(120), nullable=True),
            sa.Column("contract_start", sa.Date(), nullable=True),
            sa.Column("contract_end", sa.Date(), nullable=True),
            sa.Column("contact_name", sa.String(160), nullable=True),
            sa.Column("contact_phone", sa.String(40), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("company_id", "name", name="uq_contractor_company_name"),
        )

    def contractor_workers():
        op.create_table(
            "contractor_workers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("contractor_id", sa.Integer(), sa.ForeignKey("contractor_companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("full_name", sa.String(160), nullable=False),
            sa.Column("national_id_masked", sa.String(20), nullable=True),
            sa.Column("job_title", sa.String(120), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("contractor_id", "full_name", name="uq_contractor_worker_name"),
        )

    def contractor_documents():
        op.create_table(
            "contractor_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("contractor_id", sa.Integer(), sa.ForeignKey("contractor_companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_type", sa.String(60), nullable=False),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=True),
            sa.Column("storage_key", sa.String(500), nullable=True),
            sa.Column("content_type", sa.String(120), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("valid_until", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("document_record_id", sa.Integer(), sa.ForeignKey("document_records.id"), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    def visitor_passes():
        op.create_table(
            "visitor_passes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("full_name", sa.String(160), nullable=False),
            sa.Column("organization", sa.String(220), nullable=True),
            sa.Column("phone", sa.String(40), nullable=True),
            sa.Column("purpose", sa.String(500), nullable=False),
            sa.Column("valid_from", sa.DateTime(), nullable=False),
            sa.Column("valid_until", sa.DateTime(), nullable=False),
            sa.Column("token_hash", sa.String(128), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="issued"),
            sa.Column("checked_in_at", sa.DateTime(), nullable=True),
            sa.Column("checked_out_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.UniqueConstraint("token_hash", name="uq_visitor_pass_token_hash"),
        )

    def field_mobile_evidence():
        op.create_table(
            "field_mobile_evidence",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("entity_type", sa.String(40), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("storage_key", sa.String(500), nullable=False),
            sa.Column("original_name", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(120), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("captured_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    _create_if_missing(inspector, "contractor_companies", contractor_companies)
    inspector = sa.inspect(bind)
    _create_if_missing(inspector, "contractor_workers", contractor_workers)
    inspector = sa.inspect(bind)
    _create_if_missing(inspector, "contractor_documents", contractor_documents)
    inspector = sa.inspect(bind)
    _create_if_missing(inspector, "work_permits", work_permits)
    inspector = sa.inspect(bind)
    if inspector.has_table("work_permits") and inspector.has_table("contractor_companies"):
        wp_cols = {c["name"] for c in inspector.get_columns("work_permits")}
        if "contractor_id" in wp_cols:
            fks = inspector.get_foreign_keys("work_permits")
            has_fk = any(item.get("constrained_columns") == ["contractor_id"] for item in fks)
            if not has_fk:
                op.create_foreign_key(
                    "fk_work_permits_contractor_id",
                    "work_permits",
                    "contractor_companies",
                    ["contractor_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
    inspector = sa.inspect(bind)
    _create_if_missing(inspector, "work_permit_employees", work_permit_employees)
    inspector = sa.inspect(bind)
    _create_if_missing(inspector, "work_permit_controls", work_permit_controls)
    inspector = sa.inspect(bind)
    _create_if_missing(inspector, "work_permit_approvers", work_permit_approvers)
    inspector = sa.inspect(bind)
    _create_if_missing(inspector, "visitor_passes", visitor_passes)
    inspector = sa.inspect(bind)
    _create_if_missing(inspector, "field_mobile_evidence", field_mobile_evidence)

    if bind.dialect.name != "postgresql":
        return

    company_tables = {
        "work_permits": "company_id",
        "contractor_companies": "company_id",
        "visitor_passes": "company_id",
        "field_mobile_evidence": "company_id",
    }
    child_tables = {
        "contractor_workers": ("contractor_id", "contractor_companies"),
        "contractor_documents": ("contractor_id", "contractor_companies"),
        "work_permit_employees": ("permit_id", "work_permits"),
        "work_permit_controls": ("permit_id", "work_permits"),
        "work_permit_approvers": ("permit_id", "work_permits"),
    }
    inspector = sa.inspect(bind)
    for table, column in company_tables.items():
        if not inspector.has_table(table):
            continue
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        scope = f"{table}.{column} = ANY(string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[])"
        op.execute(sa.text(f"""
            DO $policy$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = current_schema() AND tablename = '{table}' AND policyname = '{table}_company_scope') THEN
                CREATE POLICY {table}_company_scope ON {table} FOR ALL
                USING (COALESCE(current_setting('app.current_user_id', true), '') = '' OR COALESCE(current_setting('app.rls_bypass', true), '') = '1' OR (COALESCE(current_setting('app.allowed_company_ids', true), '') <> '' AND {scope}))
                WITH CHECK (COALESCE(current_setting('app.current_user_id', true), '') = '' OR COALESCE(current_setting('app.rls_bypass', true), '') = '1' OR (COALESCE(current_setting('app.allowed_company_ids', true), '') <> '' AND {scope}));
              END IF;
            END $policy$;
        """))
    for table, (fk_col, parent) in child_tables.items():
        if not inspector.has_table(table):
            continue
        parent_col = "id"
        company_col = "company_id"
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        scope = (
            f"EXISTS (SELECT 1 FROM {parent} p WHERE p.{parent_col} = {table}.{fk_col} "
            f"AND COALESCE(current_setting('app.allowed_company_ids', true), '') <> '' "
            f"AND p.{company_col} = ANY(string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]))"
        )
        op.execute(sa.text(f"""
            DO $policy$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = current_schema() AND tablename = '{table}' AND policyname = '{table}_company_scope') THEN
                CREATE POLICY {table}_company_scope ON {table} FOR ALL
                USING (COALESCE(current_setting('app.current_user_id', true), '') = '' OR COALESCE(current_setting('app.rls_bypass', true), '') = '1' OR {scope})
                WITH CHECK (COALESCE(current_setting('app.current_user_id', true), '') = '' OR COALESCE(current_setting('app.rls_bypass', true), '') = '1' OR {scope});
              END IF;
            END $policy$;
        """))


def downgrade() -> None:
    pass
