"""EİSA error / support reports table.
Revision ID: 0022
Revises: 0021
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("eisa_error_reports"):
        return
    op.create_table(
        "eisa_error_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("osgb_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("user_role", sa.String(40), nullable=True),
        sa.Column("page_path", sa.String(500), nullable=True),
        sa.Column("http_method", sa.String(16), nullable=True),
        sa.Column("http_path", sa.String(500), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(220), nullable=False),
        sa.Column("message", sa.String(4000), nullable=True),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("user_note", sa.String(2000), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("admin_note", sa.String(2000), nullable=True),
        sa.Column("admin_reply", sa.String(2000), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_eisa_error_reports_source", "eisa_error_reports", ["source"])
    op.create_index("ix_eisa_error_reports_status", "eisa_error_reports", ["status"])
    op.create_index("ix_eisa_error_reports_user_id", "eisa_error_reports", ["user_id"])
    op.create_index("ix_eisa_error_reports_osgb_id", "eisa_error_reports", ["osgb_id"])
    op.create_index("ix_eisa_error_reports_created_at", "eisa_error_reports", ["created_at"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("eisa_error_reports"):
        op.drop_table("eisa_error_reports")
