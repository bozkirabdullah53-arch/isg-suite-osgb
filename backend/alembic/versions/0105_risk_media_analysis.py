"""Risk media AI analysis table (saha fotoğrafı AI analizi, 0.9.246).

Additive: yeni tablo. Mevcut risk_media tablosuna/mantığına dokunmaz.
Revision ID: 0105_risk_media_analysis
Revises: 0104_ppe_inventory_management
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0105_risk_media_analysis"
down_revision: Union[str, None] = "0104_ppe_inventory_management"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("risk_media_analyses"):
        return
    op.create_table(
        "risk_media_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("engine", sa.String(40), nullable=True),
        sa.Column("provider", sa.String(30), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("analysis_json", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(2000), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["media_id"], ["risk_media.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
    )
    op.create_index("ix_risk_media_analyses_media_id", "risk_media_analyses", ["media_id"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("risk_media_analyses"):
        return
    op.drop_index("ix_risk_media_analyses_media_id", table_name="risk_media_analyses")
    op.drop_table("risk_media_analyses")
