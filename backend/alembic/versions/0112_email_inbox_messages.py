"""Add Global IMAP inbox message storage."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0112_email_inbox_messages"
down_revision: Union[str, None] = "0111_emergency_plan_compliance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("email_inbox_messages"):
        return
    op.create_table(
        "email_inbox_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mailbox", sa.String(length=160), nullable=False, server_default="INBOX"),
        sa.Column("imap_uid", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=500), nullable=True),
        sa.Column("sender_email", sa.String(length=255), nullable=True),
        sa.Column("sender_name", sa.String(length=160), nullable=True),
        sa.Column("recipients", sa.String(length=2000), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for name, column in (
        ("ix_email_inbox_messages_mailbox", "mailbox"),
        ("ix_email_inbox_messages_imap_uid", "imap_uid"),
        ("ix_email_inbox_messages_message_id", "message_id"),
        ("ix_email_inbox_messages_sender_email", "sender_email"),
        ("ix_email_inbox_messages_is_read", "is_read"),
        ("ix_email_inbox_messages_received_at", "received_at"),
        ("ix_email_inbox_messages_synced_at", "synced_at"),
    ):
        op.create_index(name, "email_inbox_messages", [column])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("email_inbox_messages"):
        return
    for name in (
        "ix_email_inbox_messages_synced_at",
        "ix_email_inbox_messages_received_at",
        "ix_email_inbox_messages_is_read",
        "ix_email_inbox_messages_sender_email",
        "ix_email_inbox_messages_message_id",
        "ix_email_inbox_messages_imap_uid",
        "ix_email_inbox_messages_mailbox",
    ):
        op.drop_index(name, table_name="email_inbox_messages")
    op.drop_table("email_inbox_messages")
