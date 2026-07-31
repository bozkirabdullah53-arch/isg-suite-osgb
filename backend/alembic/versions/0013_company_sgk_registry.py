"""Add companies.sgk_registry_no (işyeri sicil no).
Revision ID: 0013
Revises: 0012
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    if "sgk_registry_no" not in cols:
        op.add_column("companies", sa.Column("sgk_registry_no", sa.String(40), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    if "sgk_registry_no" in cols:
        op.drop_column("companies", "sgk_registry_no")
