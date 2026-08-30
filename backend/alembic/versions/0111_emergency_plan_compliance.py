"""Acil durum planı mevzuat alanları.

Revision ID: 0111_emergency_plan_compliance
Revises: 0110_indiv_app_deleted
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0111_emergency_plan_compliance"
down_revision: Union[str, None] = "0110_indiv_app_deleted"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = "emergency_plans"
_COLUMN = "plan_details_json"


def _has_column() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return _COLUMN in {column["name"] for column in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    if not _has_column():
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column():
        op.drop_column(_TABLE, _COLUMN)
