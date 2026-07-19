"""Risk assessment module tables.
Revision ID: 0005
Revises: 0004

FK constraints omitted intentionally — avoids SQLAlchemy f405 on Render when
referred tables are not in the same CreateTable metadata batch. App lifespan
create_all / later migrations can add constraints if needed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade():
    if not _has("hazard_categories"):
        op.create_table(
            "hazard_categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(150), nullable=False),
            sa.Column("icon", sa.String(50), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
        )
        op.create_index("ix_hazard_categories_name", "hazard_categories", ["name"], unique=True)

    if not _has("hazards"):
        op.create_table(
            "hazards",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(20), nullable=False),
            sa.Column("name", sa.String(250), nullable=False),
            sa.Column("description", sa.String(2000), nullable=True),
            sa.Column("risk_source", sa.String(250), nullable=True),
            sa.Column("regulations", sa.String(4000), nullable=True),
            sa.Column("ai_suggestions", sa.String(4000), nullable=True),
            sa.Column("default_probability", sa.Integer(), nullable=True),
            sa.Column("default_severity", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_hazards_category_id", "hazards", ["category_id"])
        op.create_index("ix_hazards_code", "hazards", ["code"], unique=True)
        op.create_index("ix_hazards_name", "hazards", ["name"])

    # department_id added in 0006
    if not _has("risk_assessments"):
        op.create_table(
            "risk_assessments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("risk_code", sa.String(20), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("branch_id", sa.Integer(), nullable=True),
            sa.Column("hazard_id", sa.Integer(), nullable=False),
            sa.Column("department_name", sa.String(200), nullable=True),
            sa.Column("activity", sa.String(500), nullable=False),
            sa.Column("risk_definition", sa.String(2000), nullable=False),
            sa.Column("affected_people", sa.String(500), nullable=True),
            sa.Column("affected_group", sa.String(100), nullable=True),
            sa.Column("existing_measures", sa.String(2000), nullable=True),
            sa.Column("additional_measures", sa.String(2000), nullable=True),
            sa.Column("probability", sa.Integer(), nullable=False),
            sa.Column("severity", sa.Integer(), nullable=False),
            sa.Column("risk_score", sa.Integer(), nullable=False),
            sa.Column("risk_level", sa.String(50), nullable=False),
            sa.Column("term_days", sa.Integer(), nullable=True),
            sa.Column("term_date", sa.Date(), nullable=True),
            sa.Column("term_suggested", sa.Integer(), nullable=True),
            sa.Column("term_overridden", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("status", sa.String(50), server_default="Açık"),
            sa.Column("revision_no", sa.Integer(), server_default="0"),
            sa.Column("created_by_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_risk_assessments_risk_code", "risk_assessments", ["risk_code"], unique=True)
        op.create_index("ix_risk_assessments_company_id", "risk_assessments", ["company_id"])
        op.create_index("ix_risk_assessments_branch_id", "risk_assessments", ["branch_id"])
        op.create_index("ix_risk_assessments_hazard_id", "risk_assessments", ["hazard_id"])
        op.create_index("ix_risk_assessments_risk_score", "risk_assessments", ["risk_score"])
        op.create_index("ix_risk_assessments_risk_level", "risk_assessments", ["risk_level"])
        op.create_index("ix_risk_assessments_status", "risk_assessments", ["status"])

    if not _has("risk_dofs"):
        op.create_table(
            "risk_dofs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("dof_code", sa.String(20), nullable=False),
            sa.Column("risk_id", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(2000), nullable=False),
            sa.Column("responsible_person", sa.String(150), nullable=True),
            sa.Column("responsible_department", sa.String(150), nullable=True),
            sa.Column("term_date", sa.Date(), nullable=True),
            sa.Column("completion_date", sa.Date(), nullable=True),
            sa.Column("cost_estimate", sa.Integer(), nullable=True),
            sa.Column("currency", sa.String(10), server_default="TRY"),
            sa.Column("status", sa.String(50), server_default="Açık"),
            sa.Column("completion_note", sa.String(2000), nullable=True),
            sa.Column("is_completed", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("created_by_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_risk_dofs_dof_code", "risk_dofs", ["dof_code"], unique=True)
        op.create_index("ix_risk_dofs_risk_id", "risk_dofs", ["risk_id"])
        op.create_index("ix_risk_dofs_status", "risk_dofs", ["status"])


def downgrade():
    for name in ("risk_dofs", "risk_assessments", "hazards", "hazard_categories"):
        if _has(name):
            op.drop_table(name)
