"""Sürümlü eğitim soru bankası ve sabit sınav kopyaları.

Revision ID: 0068
Revises: 0067
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0068"
down_revision: Union[str, None] = "0067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("training_questions"):
        op.create_table(
            "training_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("question_code", sa.String(60), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("topic_code", sa.String(100), nullable=False),
            sa.Column("topic_label", sa.String(300), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("option_a", sa.Text(), nullable=False),
            sa.Column("option_b", sa.Text(), nullable=False),
            sa.Column("option_c", sa.Text(), nullable=False),
            sa.Column("option_d", sa.Text(), nullable=False),
            sa.Column("correct_option", sa.String(1), nullable=False),
            sa.Column("answer_explanation", sa.Text(), nullable=False),
            sa.Column("reviewer_note", sa.Text(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("retired_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("correct_option IN ('A','B','C','D')", name="ck_training_question_correct_option"),
            sa.CheckConstraint("status IN ('draft','in_review','published','retired')", name="ck_training_question_status"),
            sa.UniqueConstraint("question_code", "version", name="uq_training_question_code_version"),
        )
        op.create_index("ix_training_questions_question_code", "training_questions", ["question_code"])
        op.create_index("ix_training_questions_status", "training_questions", ["status"])
        op.create_index("ix_training_questions_topic_code", "training_questions", ["topic_code"])
        op.create_index("ix_training_questions_created_by_id", "training_questions", ["created_by_id"])
        op.create_index("ix_training_questions_published_at", "training_questions", ["published_at"])

    if not insp.has_table("training_question_scopes"):
        op.create_table(
            "training_question_scopes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("training_questions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("scope_type", sa.String(20), nullable=False),
            sa.Column("scope_value", sa.String(140), nullable=False, server_default="*"),
            sa.CheckConstraint("scope_type IN ('common','hazard','sector','nace')", name="ck_training_question_scope_type"),
            sa.UniqueConstraint("question_id", "scope_type", "scope_value", name="uq_training_question_scope"),
        )
        op.create_index("ix_training_question_scopes_question_id", "training_question_scopes", ["question_id"])
        op.create_index("ix_training_question_scopes_scope_type", "training_question_scopes", ["scope_type"])
        op.create_index("ix_training_question_scopes_scope_value", "training_question_scopes", ["scope_value"])

    if not insp.has_table("training_question_sources"):
        op.create_table(
            "training_question_sources",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("training_questions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("url", sa.String(1000), nullable=False),
            sa.Column("reference", sa.String(300), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=True),
            sa.Column("checked_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_training_question_sources_question_id", "training_question_sources", ["question_id"])

    if not insp.has_table("training_exam_snapshots"):
        op.create_table(
            "training_exam_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("training_id", sa.Integer(), sa.ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("question_count", sa.Integer(), nullable=False, server_default="15"),
            sa.Column("random_seed", sa.String(80), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("selection_policy", sa.String(80), nullable=False, server_default="approved-5x3-v1"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("training_id", "version", name="uq_training_exam_snapshot_version"),
        )
        op.create_index("ix_training_exam_snapshots_training_id", "training_exam_snapshots", ["training_id"])
        op.create_index("ix_training_exam_snapshots_content_hash", "training_exam_snapshots", ["content_hash"])
        op.create_index("ix_training_exam_snapshots_created_by_id", "training_exam_snapshots", ["created_by_id"])
        op.create_index("ix_training_exam_snapshots_created_at", "training_exam_snapshots", ["created_at"])

    if not insp.has_table("training_exam_snapshot_items"):
        op.create_table(
            "training_exam_snapshot_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("exam_id", sa.Integer(), sa.ForeignKey("training_exam_snapshots.id", ondelete="CASCADE"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("training_questions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("question_code", sa.String(60), nullable=False),
            sa.Column("question_version", sa.Integer(), nullable=False),
            sa.Column("topic_code", sa.String(100), nullable=False),
            sa.Column("topic_label", sa.String(300), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("options_json", sa.Text(), nullable=False),
            sa.Column("correct_option", sa.String(1), nullable=False),
            sa.Column("answer_explanation", sa.Text(), nullable=False),
            sa.Column("sources_json", sa.Text(), nullable=False),
            sa.Column("scopes_json", sa.Text(), nullable=False),
            sa.CheckConstraint("correct_option IN ('A','B','C','D')", name="ck_training_exam_correct_option"),
            sa.UniqueConstraint("exam_id", "position", name="uq_training_exam_item_position"),
        )
        op.create_index("ix_training_exam_snapshot_items_exam_id", "training_exam_snapshot_items", ["exam_id"])
        op.create_index("ix_training_exam_snapshot_items_question_id", "training_exam_snapshot_items", ["question_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in (
        "training_exam_snapshot_items",
        "training_exam_snapshots",
        "training_question_sources",
        "training_question_scopes",
        "training_questions",
    ):
        if insp.has_table(table):
            op.drop_table(table)
