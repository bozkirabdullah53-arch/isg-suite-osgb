"""Revision ID: 0020
Revises: 0019
Company: address, phone, authorized_person
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    if "address" not in cols:
        op.add_column("companies", sa.Column("address", sa.String(500), nullable=True))
    if "phone" not in cols:
        op.add_column("companies", sa.Column("phone", sa.String(40), nullable=True))
    if "authorized_person" not in cols:
        op.add_column("companies", sa.Column("authorized_person", sa.String(160), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    if "authorized_person" in cols:
        op.drop_column("companies", "authorized_person")
    if "phone" in cols:
        op.drop_column("companies", "phone")
    if "address" in cols:
        op.drop_column("companies", "address")
