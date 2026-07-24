"""Geçici (TTL) işyeri saha QR oturumları.
Revision ID: 0036
Revises: 0035
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("site_qr_sessions"):
        return
    op.create_table(
        "site_qr_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_site_qr_sessions_company_id", "site_qr_sessions", ["company_id"])
    op.create_index("ix_site_qr_sessions_token", "site_qr_sessions", ["token"], unique=True)
    op.create_index("ix_site_qr_sessions_expires_at", "site_qr_sessions", ["expires_at"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("site_qr_sessions"):
        return
    op.drop_index("ix_site_qr_sessions_expires_at", table_name="site_qr_sessions")
    op.drop_index("ix_site_qr_sessions_token", table_name="site_qr_sessions")
    op.drop_index("ix_site_qr_sessions_company_id", table_name="site_qr_sessions")
    op.drop_table("site_qr_sessions")
