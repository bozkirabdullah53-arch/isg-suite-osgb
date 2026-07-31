"""Annual eval verify_code.
Revision ID: 0034
Revises: 0033
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("annual_plan_evaluations"):
        return
    cols = {c["name"] for c in insp.get_columns("annual_plan_evaluations")}
    if "verify_code" not in cols:
        op.add_column(
            "annual_plan_evaluations",
            sa.Column("verify_code", sa.String(40), nullable=True),
        )
        op.create_index("ix_annual_plan_evaluations_verify_code", "annual_plan_evaluations", ["verify_code"], unique=True)


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("annual_plan_evaluations"):
        return
    cols = {c["name"] for c in insp.get_columns("annual_plan_evaluations")}
    if "verify_code" in cols:
        op.drop_index("ix_annual_plan_evaluations_verify_code", table_name="annual_plan_evaluations")
        op.drop_column("annual_plan_evaluations", "verify_code")
