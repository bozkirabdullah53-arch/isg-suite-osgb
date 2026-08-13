"""Add the opt-in strict policy for remote OHS pilot packages.

The migration is additive.  Existing company programs are explicitly marked
legacy and keep their current thresholds and progress semantics.  Central
catalog packages receive the strict defaults because they have not yet been
assigned to a company; materialization snapshots those settings into a new
company program.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0092_remote_ohs_strict"
down_revision: Union[str, None] = "0091_remote_ohs_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {item["name"] for item in inspector.get_columns(table)}


def _indexes(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {item["name"] for item in inspector.get_indexes(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    if table in {"users", "remote_training_programs", "remote_training_catalog_packages", "remote_training_video_progress"} and column.name not in _columns(table):
        op.add_column(table, column)


def _add_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    if name not in _indexes(table):
        op.create_index(name, table, columns)


def _drop_index_if_exists(name: str, table: str) -> None:
    if name in _indexes(table):
        op.drop_index(name, table_name=table)


def _foreign_keys(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {item.get("name") for item in inspector.get_foreign_keys(table) if item.get("name")}


def upgrade() -> None:
    bind = op.get_bind()

    if sa.inspect(bind).has_table("users"):
        _add_column_if_missing(
            "users",
            sa.Column("password_change_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if sa.inspect(bind).has_table("remote_training_programs"):
        _add_column_if_missing("remote_training_programs", sa.Column("source_catalog_package_id", sa.Integer(), nullable=True))
        _add_column_if_missing("remote_training_programs", sa.Column("source_catalog_code", sa.String(96), nullable=True))
        _add_column_if_missing("remote_training_programs", sa.Column("source_catalog_revision_no", sa.Integer(), nullable=True))
        _add_column_if_missing("remote_training_programs", sa.Column("policy_mode", sa.String(24), nullable=False, server_default="legacy"))
        _add_column_if_missing("remote_training_programs", sa.Column("sequence_enforced", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add_column_if_missing("remote_training_programs", sa.Column("exam_gate_enforced", sa.Boolean(), nullable=False, server_default=sa.false()))
        if bind.dialect.name != "sqlite" and "fk_remote_program_source_catalog_package" not in _foreign_keys("remote_training_programs"):
            op.create_foreign_key(
                "fk_remote_program_source_catalog_package",
                "remote_training_programs",
                "remote_training_catalog_packages",
                ["source_catalog_package_id"],
                ["id"],
                ondelete="SET NULL",
            )
        _add_index_if_missing(
            "ix_remote_training_programs_source_catalog_package",
            "remote_training_programs",
            ["source_catalog_package_id"],
        )
        _add_index_if_missing(
            "ix_remote_training_programs_source_catalog_code",
            "remote_training_programs",
            ["source_catalog_code"],
        )

    if sa.inspect(bind).has_table("remote_training_catalog_packages"):
        _add_column_if_missing("remote_training_catalog_packages", sa.Column("policy_mode", sa.String(24), nullable=False, server_default="strict"))
        _add_column_if_missing("remote_training_catalog_packages", sa.Column("sequence_enforced", sa.Boolean(), nullable=False, server_default=sa.true()))
        _add_column_if_missing("remote_training_catalog_packages", sa.Column("exam_gate_enforced", sa.Boolean(), nullable=False, server_default=sa.true()))
        # Catalog rows are not employee history.  Normalize them to the common
        # pilot rule without touching any company-scoped program.
        op.execute(
            sa.text(
                "UPDATE remote_training_catalog_packages "
                "SET completion_threshold_percent = 100, passing_score = 70, "
                "policy_mode = 'strict', sequence_enforced = TRUE, exam_gate_enforced = TRUE"
            )
        )

    if sa.inspect(bind).has_table("remote_training_video_progress"):
        _add_column_if_missing(
            "remote_training_video_progress",
            sa.Column("coverage_json", sa.Text(), nullable=True, server_default="[]"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("users") and "password_change_required" in _columns("users"):
        op.drop_column("users", "password_change_required")

    if inspector.has_table("remote_training_video_progress") and "coverage_json" in _columns("remote_training_video_progress"):
        op.drop_column("remote_training_video_progress", "coverage_json")

    if inspector.has_table("remote_training_catalog_packages"):
        for column in ("exam_gate_enforced", "sequence_enforced", "policy_mode"):
            if column in _columns("remote_training_catalog_packages"):
                op.drop_column("remote_training_catalog_packages", column)

    if inspector.has_table("remote_training_programs"):
        _drop_index_if_exists("ix_remote_training_programs_source_catalog_code", "remote_training_programs")
        _drop_index_if_exists("ix_remote_training_programs_source_catalog_package", "remote_training_programs")
        if bind.dialect.name != "sqlite" and "fk_remote_program_source_catalog_package" in _foreign_keys("remote_training_programs"):
            op.drop_constraint("fk_remote_program_source_catalog_package", "remote_training_programs", type_="foreignkey")
        for column in (
            "exam_gate_enforced",
            "sequence_enforced",
            "policy_mode",
            "source_catalog_revision_no",
            "source_catalog_code",
            "source_catalog_package_id",
        ):
            if column in _columns("remote_training_programs"):
                op.drop_column("remote_training_programs", column)
