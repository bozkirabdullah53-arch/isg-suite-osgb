"""Additive employee pre-assessment for remote Basic OHS training.

Existing training, video, final-exam, progress and certificate records are
preserved.  The new question marker and one-attempt result table are
backward-compatible additions.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0105_remote_pre_assessment"
down_revision: Union[str, None] = "0104_ppe_inventory_management"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table: str) -> bool:
    return sa.inspect(bind).has_table(table)


def _columns(bind, table: str) -> set[str]:
    if not _table_exists(bind, table):
        return set()
    return {item["name"] for item in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    if not _table_exists(bind, table):
        return set()
    return {str(item.get("name")) for item in sa.inspect(bind).get_indexes(table) if item.get("name")}


def _enable_rls(bind, table: str) -> None:
    if bind.dialect.name != "postgresql" or not _table_exists(bind, table):
        return
    policy = f"{table}_company_scope"
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            f"""
            DO $policy$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = current_schema()
                  AND tablename = '{table}'
                  AND policyname = '{policy}'
              ) THEN
                CREATE POLICY "{policy}" ON "{table}"
                  FOR ALL
                  USING (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                    OR (
                      COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                      AND "{table}".company_id = ANY (
                        string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                      )
                    )
                  )
                  WITH CHECK (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                    OR (
                      COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                      AND "{table}".company_id = ANY (
                        string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                      )
                    )
                  );
              END IF;
            END
            $policy$;
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    question_table = "remote_training_questions"
    if _table_exists(bind, question_table):
        columns = _columns(bind, question_table)
        if "is_pre_assessment" not in columns:
            op.add_column(
                question_table,
                sa.Column(
                    "is_pre_assessment",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )
        if "ix_remote_training_questions_pre_assessment" not in _indexes(bind, question_table):
            op.create_index(
                "ix_remote_training_questions_pre_assessment",
                question_table,
                ["is_pre_assessment"],
            )

    attempt_table = "remote_training_pre_assessment_attempts"
    if not _table_exists(bind, attempt_table):
        op.create_table(
            attempt_table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "company_id",
                sa.Integer(),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "program_id",
                sa.Integer(),
                sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "assignment_id",
                sa.Integer(),
                sa.ForeignKey("remote_training_assignments.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "employee_id",
                sa.Integer(),
                sa.ForeignKey("employees.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("question_ids_json", sa.Text(), nullable=False),
            sa.Column("answers_json", sa.Text(), nullable=False),
            sa.Column("question_count", sa.Integer(), nullable=False),
            sa.Column("correct_count", sa.Integer(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(), nullable=False),
            sa.Column(
                "submitted_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.UniqueConstraint("assignment_id", name="uq_remote_pre_assessment_assignment"),
        )
        op.create_index(
            "ix_remote_pre_assessment_attempts_company",
            attempt_table,
            ["company_id"],
        )
        op.create_index(
            "ix_remote_pre_assessment_attempts_assignment",
            attempt_table,
            ["assignment_id"],
        )
    _enable_rls(bind, attempt_table)


def downgrade() -> None:
    bind = op.get_bind()
    attempt_table = "remote_training_pre_assessment_attempts"
    if bind.dialect.name == "postgresql" and _table_exists(bind, attempt_table):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{attempt_table}_company_scope" ON "{attempt_table}"'))
        op.execute(sa.text(f'ALTER TABLE "{attempt_table}" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{attempt_table}" DISABLE ROW LEVEL SECURITY'))
    if _table_exists(bind, attempt_table):
        op.drop_table(attempt_table)

    question_table = "remote_training_questions"
    if _table_exists(bind, question_table):
        columns = _columns(bind, question_table)
        if "is_pre_assessment" in columns:
            if "ix_remote_training_questions_pre_assessment" in _indexes(bind, question_table):
                op.drop_index(
                    "ix_remote_training_questions_pre_assessment",
                    table_name=question_table,
                )
            op.drop_column(question_table, "is_pre_assessment")
