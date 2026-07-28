"""Eyas — işyeri belge kaynağı (source_key).

Revision ID: 0066
Revises: 0065
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0066"
down_revision: Union[str, None] = "0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "eyas_workflows",
        sa.Column("source_key", sa.String(length=160), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("eyas_workflows", "source_key")
