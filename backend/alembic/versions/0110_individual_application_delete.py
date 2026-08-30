"""Add a deletion marker for individual specialist applications.

Revision ID: 0110_individual_application_delete
Revises: 0109_email_delivery_logs
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0110_individual_application_delete"
down_revision: Union[str, None] = "0109_email_delivery_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "osgb_organizations"
_COLUMN = "application_deleted_at"
_INDEX = "ix_osgb_organizations_application_deleted_at"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_column() -> bool:
    return _COLUMN in {column["name"] for column in _inspector().get_columns(_TABLE)}


def _has_index() -> bool:
    return _INDEX in {index["name"] for index in _inspector().get_indexes(_TABLE)}


def upgrade() -> None:
    if not _has_column():
        op.add_column(
            _TABLE,
            sa.Column(_COLUMN, sa.DateTime(), nullable=True),
        )
    if not _has_index():
        op.create_index(_INDEX, _TABLE, [_COLUMN])


def downgrade() -> None:
    if _has_index():
        op.drop_index(_INDEX, table_name=_TABLE)
    if _has_column():
        op.drop_column(_TABLE, _COLUMN)
