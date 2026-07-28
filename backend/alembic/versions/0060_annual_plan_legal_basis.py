"""Add legal_basis to annual_plan_items (additive).

Revision ID: 0060
Revises: 0059
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0060"
down_revision: Union[str, None] = "0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("annual_plan_items"):
        return
    cols = {c["name"] for c in insp.get_columns("annual_plan_items")}
    if "legal_basis" not in cols:
        op.add_column(
            "annual_plan_items",
            sa.Column("legal_basis", sa.String(length=240), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("annual_plan_items"):
        return
    cols = {c["name"] for c in insp.get_columns("annual_plan_items")}
    if "legal_basis" in cols:
        op.drop_column("annual_plan_items", "legal_basis")
