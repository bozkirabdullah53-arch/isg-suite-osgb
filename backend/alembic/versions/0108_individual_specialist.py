"""Bireysel uzman çalışma alanı bayrağı.

Revision ID: 0108_individual_specialist
Revises: 0107_idea_premium_modules
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0108_individual_specialist"
down_revision: Union[str, None] = "0107_idea_premium_modules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "osgb_organizations"
_COLUMN = "is_individual"


def _has_column() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return _COLUMN in {column["name"] for column in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    if not _has_column():
        op.add_column(
            _TABLE,
            sa.Column(_COLUMN, sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    op.execute(
        sa.text(
            """
            UPDATE osgb_organizations
            SET is_individual = true
            WHERE authorization_number LIKE 'MOBIL-%'
               OR authorization_number LIKE 'IND-%'
               OR name ILIKE '%Bireysel Uzman%'
            """
        )
    )


def downgrade() -> None:
    if _has_column():
        op.drop_column(_TABLE, _COLUMN)
