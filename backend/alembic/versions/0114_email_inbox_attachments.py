"""Store safe metadata and bytes for Global inbox attachments."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0114_email_inbox_attachments"
down_revision: Union[str, None] = "0113_email_inbox_deleted_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("email_inbox_attachments"):
        return
    op.create_table(
        "email_inbox_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("email_inbox_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False, server_default="ek-dosya"),
        sa.Column("content_type", sa.String(length=160), nullable=False, server_default="application/octet-stream"),
        sa.Column("content_id", sa.String(length=500), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_email_inbox_attachments_message_id", "email_inbox_attachments", ["message_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("email_inbox_attachments"):
        return
    op.drop_index("ix_email_inbox_attachments_message_id", table_name="email_inbox_attachments")
    op.drop_table("email_inbox_attachments")
