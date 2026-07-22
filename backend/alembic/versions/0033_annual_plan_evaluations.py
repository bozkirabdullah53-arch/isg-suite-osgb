"""Annual plan evaluation tables.
Revision ID: 0033
Revises: 0032
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("annual_plan_evaluations"):
        op.create_table(
            "annual_plan_evaluations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
            sa.Column("report_status", sa.String(40), nullable=False, server_default="hazirlaniyor"),
            sa.Column("report_date", sa.Date(), nullable=True),
            sa.Column("specialist_name", sa.String(160), nullable=True),
            sa.Column("physician_name", sa.String(160), nullable=True),
            sa.Column("employer_name", sa.String(160), nullable=True),
            sa.Column("plan_item_count_at_start", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_annual_plan_evaluations_company_id", "annual_plan_evaluations", ["company_id"])
        op.create_index("ix_annual_plan_evaluations_year", "annual_plan_evaluations", ["year"])
    if not insp.has_table("annual_plan_evaluation_items"):
        op.create_table(
            "annual_plan_evaluation_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("annual_plan_evaluations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("plan_item_id", sa.Integer(), sa.ForeignKey("annual_plan_items.id"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("outcome_status", sa.String(40), nullable=False, server_default="planlandi"),
            sa.Column("actual_start", sa.Date(), nullable=True),
            sa.Column("actual_end", sa.Date(), nullable=True),
            sa.Column("completion_pct", sa.Integer(), nullable=True),
            sa.Column("result_text", sa.String(4000), nullable=True),
            sa.Column("deviation_reason", sa.String(2000), nullable=True),
            sa.Column("delay_days", sa.Integer(), nullable=True),
            sa.Column("specialist_note", sa.String(2000), nullable=True),
            sa.Column("physician_note", sa.String(2000), nullable=True),
            sa.Column("employer_note", sa.String(2000), nullable=True),
            sa.Column("next_year_suggestion", sa.String(2000), nullable=True),
            sa.Column("target_met", sa.Boolean(), nullable=True),
            sa.Column("capa_needed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("plan_item_id", name="uq_annual_eval_plan_item"),
        )
        op.create_index("ix_annual_plan_evaluation_items_evaluation_id", "annual_plan_evaluation_items", ["evaluation_id"])
        op.create_index("ix_annual_plan_evaluation_items_plan_item_id", "annual_plan_evaluation_items", ["plan_item_id"])
    if not insp.has_table("annual_plan_eval_evidences"):
        op.create_table(
            "annual_plan_eval_evidences",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("evaluation_item_id", sa.Integer(), sa.ForeignKey("annual_plan_evaluation_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("doc_type", sa.String(80), nullable=True),
            sa.Column("title", sa.String(200), nullable=True),
            sa.Column("doc_date", sa.Date(), nullable=True),
            sa.Column("doc_no", sa.String(80), nullable=True),
            sa.Column("storage_path", sa.String(500), nullable=True),
            sa.Column("original_name", sa.String(255), nullable=True),
            sa.Column("content_type", sa.String(120), nullable=True),
            sa.Column("notes", sa.String(1000), nullable=True),
            sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if not insp.has_table("annual_plan_unplanned_activities"):
        op.create_table(
            "annual_plan_unplanned_activities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("annual_plan_evaluations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("activity", sa.String(240), nullable=False),
            sa.Column("category", sa.String(40), nullable=True),
            sa.Column("done_date", sa.Date(), nullable=True),
            sa.Column("reason", sa.String(2000), nullable=True),
            sa.Column("result_text", sa.String(4000), nullable=True),
            sa.Column("responsible_name", sa.String(160), nullable=True),
            sa.Column("suggest_next_year", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if not insp.has_table("annual_plan_eval_capas"):
        op.create_table(
            "annual_plan_eval_capas",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("annual_plan_evaluations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("evaluation_item_id", sa.Integer(), sa.ForeignKey("annual_plan_evaluation_items.id", ondelete="SET NULL"), nullable=True),
            sa.Column("title", sa.String(240), nullable=False),
            sa.Column("root_cause", sa.String(2000), nullable=True),
            sa.Column("action", sa.String(2000), nullable=True),
            sa.Column("responsible", sa.String(160), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("priority", sa.String(40), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="acik"),
            sa.Column("closed_at", sa.Date(), nullable=True),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for t in (
        "annual_plan_eval_capas",
        "annual_plan_unplanned_activities",
        "annual_plan_eval_evidences",
        "annual_plan_evaluation_items",
        "annual_plan_evaluations",
    ):
        if insp.has_table(t):
            op.drop_table(t)
