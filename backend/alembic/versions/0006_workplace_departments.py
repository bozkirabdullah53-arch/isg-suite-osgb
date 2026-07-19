"""Workplace departments for risk assessments.
Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("workplace_departments"):
        op.create_table(
            "workplace_departments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("company_id", "name", name="uq_workplace_department_company_name"),
        )
        op.create_index("ix_workplace_departments_company_id", "workplace_departments", ["company_id"])
        op.create_index("ix_workplace_departments_name", "workplace_departments", ["name"])

    if insp.has_table("risk_assessments"):
        cols = {c["name"] for c in insp.get_columns("risk_assessments")}
        if "department_id" not in cols:
            op.add_column("risk_assessments", sa.Column("department_id", sa.Integer(), nullable=True))
        fks = {fk["name"] for fk in insp.get_foreign_keys("risk_assessments")}
        if "fk_risk_assessments_department_id" not in fks:
            try:
                op.create_foreign_key(
                    "fk_risk_assessments_department_id",
                    "risk_assessments",
                    "workplace_departments",
                    ["department_id"],
                    ["id"],
                )
            except Exception:
                pass
        indexes = {ix["name"] for ix in insp.get_indexes("risk_assessments")}
        if "ix_risk_assessments_department_id" not in indexes:
            try:
                op.create_index(
                    "ix_risk_assessments_department_id",
                    "risk_assessments",
                    ["department_id"],
                )
            except Exception:
                pass


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("risk_assessments"):
        try:
            op.drop_constraint("fk_risk_assessments_department_id", "risk_assessments", type_="foreignkey")
        except Exception:
            pass
        try:
            op.drop_index("ix_risk_assessments_department_id", table_name="risk_assessments")
        except Exception:
            pass
        cols = {c["name"] for c in insp.get_columns("risk_assessments")}
        if "department_id" in cols:
            op.drop_column("risk_assessments", "department_id")
    if insp.has_table("workplace_departments"):
        op.drop_table("workplace_departments")
