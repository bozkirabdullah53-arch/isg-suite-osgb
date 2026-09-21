"""risk_assessments: numeric exposed worker count (İBYS hazard dataset).

The İBYS hazard-source dataset requires the number of exposed workers as a
numeric value. ``affected_people``/``affected_group`` remain as free text;
this adds an optional, additive integer column (nullable — historical rows
are untouched).

Revision ID: 0123
Revises: 0122
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0123"
down_revision: Union[str, None] = "0122"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "risk_assessments" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("risk_assessments")}
    if "exposed_worker_count" in cols:
        return
    with op.batch_alter_table("risk_assessments") as batch:
        batch.add_column(sa.Column("exposed_worker_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "risk_assessments" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("risk_assessments")}
    if "exposed_worker_count" not in cols:
        return
    with op.batch_alter_table("risk_assessments") as batch:
        batch.drop_column("exposed_worker_count")
