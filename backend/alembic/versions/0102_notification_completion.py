"""Add persistent completion state for in-app notifications."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0102_notification_completion"
down_revision: Union[str, None] = "0101_remote_employee_usernames"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("notifications"):
        return
    columns = {c["name"] for c in inspector.get_columns("notifications")}
    if "is_completed" not in columns:
        op.add_column(
            "notifications",
            sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("notifications", "is_completed", server_default=None)
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("notifications") if i.get("name")}
    if "ix_notifications_is_completed" not in indexes:
        op.create_index("ix_notifications_is_completed", "notifications", ["is_completed"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("notifications"):
        return
    indexes = {i["name"] for i in inspector.get_indexes("notifications") if i.get("name")}
    if "ix_notifications_is_completed" in indexes:
        op.drop_index("ix_notifications_is_completed", table_name="notifications")
    columns = {c["name"] for c in inspector.get_columns("notifications")}
    if "is_completed" in columns:
        op.drop_column("notifications", "is_completed")
