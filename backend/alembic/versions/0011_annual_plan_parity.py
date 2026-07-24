"""Annual plan PRO parity columns.
Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("annual_plan_items"):
        return
    cols = {c["name"] for c in insp.get_columns("annual_plan_items")}
    if "category" not in cols:
        op.add_column("annual_plan_items", sa.Column("category", sa.String(40), nullable=True))
    if "description" not in cols:
        op.add_column("annual_plan_items", sa.Column("description", sa.String(2000), nullable=True))
    if "target_date" not in cols:
        op.add_column("annual_plan_items", sa.Column("target_date", sa.Date(), nullable=True))
    if "deleted_at" not in cols:
        op.add_column("annual_plan_items", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    # Postgres enum: cancelled (best-effort; native_enum=False DB'lerde tip yok olabilir)
    from app.core.pg_enum import pg_add_enum_value

    pg_add_enum_value(bind, "annualplanstatus", "cancelled")


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("annual_plan_items"):
        return
    cols = {c["name"] for c in insp.get_columns("annual_plan_items")}
    for name in ("deleted_at", "target_date", "description", "category"):
        if name in cols:
            op.drop_column("annual_plan_items", name)
