"""Integration dry-run export log table.
Revision ID: 0030
Revises: 0029
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("integration_dry_run_logs"):
        return
    op.create_table(
        "integration_dry_run_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id"), nullable=True),
        sa.Column("adapter", sa.String(20), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="dry_run"),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_integration_dry_run_logs_user_id", "integration_dry_run_logs", ["user_id"])
    op.create_index("ix_integration_dry_run_logs_osgb_id", "integration_dry_run_logs", ["osgb_id"])
    op.create_index("ix_integration_dry_run_logs_adapter", "integration_dry_run_logs", ["adapter"])
    op.create_index("ix_integration_dry_run_logs_status", "integration_dry_run_logs", ["status"])
    op.create_index("ix_integration_dry_run_logs_created_at", "integration_dry_run_logs", ["created_at"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("integration_dry_run_logs"):
        return
    op.drop_table("integration_dry_run_logs")
