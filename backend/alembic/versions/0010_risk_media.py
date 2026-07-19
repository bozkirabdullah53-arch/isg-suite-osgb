"""Risk media table.
Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "risk_media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "risk_id",
            sa.Integer(),
            sa.ForeignKey("risk_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_risk_media_risk_id", "risk_media", ["risk_id"])


def downgrade():
    op.drop_table("risk_media")
