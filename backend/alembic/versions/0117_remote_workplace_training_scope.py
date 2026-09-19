"""Add explicit workplace assignment scope to remote training programs.

Existing programs remain usable by workplace accounts. New manually-created
programs can opt out, while catalog snapshots are explicitly enabled.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0117_remote_workplace_scope"
down_revision: Union[str, None] = "0116_workplace_backups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "remote_training_programs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("remote_training_programs")}
    if "workplace_assignment_allowed" not in columns:
        op.add_column(
            "remote_training_programs",
            sa.Column(
                "workplace_assignment_allowed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )
        op.alter_column(
            "remote_training_programs",
            "workplace_assignment_allowed",
            server_default=None,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "remote_training_programs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("remote_training_programs")}
    if "workplace_assignment_allowed" in columns:
        op.drop_column("remote_training_programs", "workplace_assignment_allowed")
