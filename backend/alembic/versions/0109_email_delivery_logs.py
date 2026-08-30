"""Add global e-mail delivery tracking without storing message content.

Revision ID: 0109_email_delivery_logs
Revises: 0108_individual_specialist
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0109_email_delivery_logs"
down_revision: Union[str, None] = "0108_individual_specialist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("email_delivery_logs"):
        return

    op.create_table(
        "email_delivery_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=80), nullable=False, server_default="generic"),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="smtp"),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("recipient_name", sa.String(length=160), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("osgb_id", sa.Integer(), nullable=True),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("related_type", sa.String(length=80), nullable=True),
        sa.Column("related_id", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["osgb_id"], ["osgb_organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for name, column in (
        ("ix_email_delivery_logs_event_type", "event_type"),
        ("ix_email_delivery_logs_provider", "provider"),
        ("ix_email_delivery_logs_recipient_email", "recipient_email"),
        ("ix_email_delivery_logs_status", "status"),
        ("ix_email_delivery_logs_user_id", "user_id"),
        ("ix_email_delivery_logs_osgb_id", "osgb_id"),
        ("ix_email_delivery_logs_triggered_by_user_id", "triggered_by_user_id"),
        ("ix_email_delivery_logs_related_type", "related_type"),
        ("ix_email_delivery_logs_related_id", "related_id"),
        ("ix_email_delivery_logs_created_at", "created_at"),
        ("ix_email_delivery_logs_sent_at", "sent_at"),
    ):
        op.create_index(name, "email_delivery_logs", [column])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("email_delivery_logs"):
        return
    for name in (
        "ix_email_delivery_logs_sent_at",
        "ix_email_delivery_logs_created_at",
        "ix_email_delivery_logs_related_id",
        "ix_email_delivery_logs_related_type",
        "ix_email_delivery_logs_triggered_by_user_id",
        "ix_email_delivery_logs_osgb_id",
        "ix_email_delivery_logs_user_id",
        "ix_email_delivery_logs_status",
        "ix_email_delivery_logs_recipient_email",
        "ix_email_delivery_logs_provider",
        "ix_email_delivery_logs_event_type",
    ):
        op.drop_index(name, table_name="email_delivery_logs")
    op.drop_table("email_delivery_logs")
