"""Add safe archive fields and immutable remote certificate signatories.

This migration is additive. Existing training sessions, assignments and
certificates remain intact; completed records can be archived instead of
physically deleted, and newly issued remote certificates keep the signatory
context used at issuance time.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0099_education_audit"
down_revision: Union[str, None] = "0098_restore_shared_ready"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "training_sessions" in tables:
        columns = _columns(bind, "training_sessions")
        if "archived_at" not in columns:
            op.add_column(
                "training_sessions",
                sa.Column("archived_at", sa.DateTime(), nullable=True),
            )
        if "archived_by_id" not in columns:
            op.add_column(
                "training_sessions",
                sa.Column(
                    "archived_by_id",
                    sa.Integer(),
                    sa.ForeignKey("users.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )
        if "archive_reason" not in columns:
            op.add_column(
                "training_sessions",
                sa.Column("archive_reason", sa.String(length=500), nullable=True),
            )
        indexes = {
            index["name"]
            for index in sa.inspect(bind).get_indexes("training_sessions")
        }
        if "ix_training_sessions_archived_at" not in indexes:
            op.create_index(
                "ix_training_sessions_archived_at",
                "training_sessions",
                ["archived_at"],
            )

    if "remote_training_certificates" in tables:
        columns = _columns(bind, "remote_training_certificates")
        additions = (
            ("instructor_qualification_snapshot", sa.String(length=220)),
            ("workplace_physician_snapshot", sa.String(length=160)),
            ("employer_representative_snapshot", sa.String(length=160)),
        )
        for name, column_type in additions:
            if name not in columns:
                op.add_column(
                    "remote_training_certificates",
                    sa.Column(name, column_type, nullable=True),
                )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "remote_training_certificates" in tables:
        columns = _columns(bind, "remote_training_certificates")
        for name in (
            "employer_representative_snapshot",
            "workplace_physician_snapshot",
            "instructor_qualification_snapshot",
        ):
            if name in columns:
                op.drop_column("remote_training_certificates", name)

    if "training_sessions" in tables:
        columns = _columns(bind, "training_sessions")
        try:
            op.drop_index("ix_training_sessions_archived_at", table_name="training_sessions")
        except Exception:
            pass
        if "archive_reason" in columns:
            op.drop_column("training_sessions", "archive_reason")
        if "archived_by_id" in columns:
            op.drop_column("training_sessions", "archived_by_id")
        if "archived_at" in columns:
            op.drop_column("training_sessions", "archived_at")
