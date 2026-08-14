"""Add immutable automatic final-exam markers to remote questions.

The column is additive.  Existing remote checkpoint questions and manually
linked question-bank exams retain their behavior; catalog-derived programs use
the same company-scoped question table for ten frozen final-exam items.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0097_remote_auto_exam"
down_revision: Union[str, None] = "0096_catalog_exam_repair"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("remote_training_questions"):
        return
    if "is_final_exam" not in _columns("remote_training_questions"):
        op.add_column(
            "remote_training_questions",
            sa.Column("is_final_exam", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index(
            "ix_remote_training_questions_final_exam",
            "remote_training_questions",
            ["is_final_exam"],
        )


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("remote_training_questions"):
        return
    if "is_final_exam" in _columns("remote_training_questions"):
        inspector = sa.inspect(op.get_bind())
        indexes = {item["name"] for item in inspector.get_indexes("remote_training_questions")}
        if "ix_remote_training_questions_final_exam" in indexes:
            op.drop_index(
                "ix_remote_training_questions_final_exam",
                table_name="remote_training_questions",
            )
        op.drop_column("remote_training_questions", "is_final_exam")
