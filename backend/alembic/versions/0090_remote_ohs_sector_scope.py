"""Add company-selected sector scope to remote Basic OHS training.

The migration is additive.  Existing programs without sector rows continue to
use the legacy all-content behavior; new programs receive a common-content
row and can opt into sector-specific content from the catalog.

Revision ID: 0090_remote_ohs_sector
Revises: 0089_remote_ohs_video
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0090_remote_ohs_sector"
down_revision: Union[str, None] = "0089_remote_ohs_video"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_company_rls(table: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    policy = f"{table}_company_scope"
    unset = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
    bypass = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
    allowed = (
        "string_to_array("
        "COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), ','"
        ")::integer[]"
    )
    scope = f"({unset}) OR ({bypass}) OR (company_id = ANY ({allowed}))"
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{policy}" ON "{table}" '
            f"FOR ALL USING ({scope}) WITH CHECK ({scope})"
        )
    )


def _drop_company_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_company_scope" ON "{table}"'))


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(table) and column.name not in {item["name"] for item in inspector.get_columns(table)}:
        op.add_column(table, column)


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(table) and name not in {item["name"] for item in inspector.get_indexes(table)}:
        op.create_index(name, table, columns)


def _drop_index_if_exists(name: str, table: str) -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(table) and name in {item["name"] for item in inspector.get_indexes(table)}:
        op.drop_index(name, table_name=table)


def upgrade() -> None:
    bind = op.get_bind()

    _add_column_if_missing(
        "remote_training_sections",
        sa.Column("sector_code", sa.String(64), nullable=False, server_default="common"),
    )
    _add_column_if_missing(
        "remote_training_questions",
        sa.Column("sector_code", sa.String(64), nullable=False, server_default="common"),
    )
    _add_column_if_missing(
        "remote_training_program_questions",
        sa.Column("sector_code", sa.String(64), nullable=True),
    )

    if not sa.inspect(bind).has_table("remote_training_program_sectors"):
        op.create_table(
            "remote_training_program_sectors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL")),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sector_code", sa.String(64), nullable=False),
            sa.Column("sector_name_snapshot", sa.String(180), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("program_id", "sector_code", name="uq_remote_program_sector"),
        )

    if not sa.inspect(bind).has_table("remote_training_assignment_sectors"):
        op.create_table(
            "remote_training_assignment_sectors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL")),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("sector_code", sa.String(64), nullable=False),
            sa.Column("sector_name_snapshot", sa.String(180), nullable=False),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("assignment_id", "sector_code", name="uq_remote_assignment_sector"),
        )

    indexes = (
        ("ix_remote_training_sections_sector_code", "remote_training_sections", ["sector_code"]),
        ("ix_remote_training_questions_sector_code", "remote_training_questions", ["sector_code"]),
        ("ix_remote_program_questions_sector_code", "remote_training_program_questions", ["sector_code"]),
        ("ix_remote_program_sectors_osgb", "remote_training_program_sectors", ["osgb_id"]),
        ("ix_remote_program_sectors_company", "remote_training_program_sectors", ["company_id"]),
        ("ix_remote_program_sectors_program", "remote_training_program_sectors", ["program_id"]),
        (
            "ix_remote_program_sectors_program_enabled",
            "remote_training_program_sectors",
            ["program_id", "is_enabled"],
        ),
        ("ix_remote_assignment_sectors_osgb", "remote_training_assignment_sectors", ["osgb_id"]),
        ("ix_remote_assignment_sectors_company", "remote_training_assignment_sectors", ["company_id"]),
        ("ix_remote_assignment_sectors_program", "remote_training_assignment_sectors", ["program_id"]),
        ("ix_remote_assignment_sectors_assignment", "remote_training_assignment_sectors", ["assignment_id"]),
        ("ix_remote_assignment_sectors_employee", "remote_training_assignment_sectors", ["employee_id"]),
        (
            "ix_remote_assignment_sectors_assignment_employee",
            "remote_training_assignment_sectors",
            ["assignment_id", "employee_id"],
        ),
    )
    for name, table, columns in indexes:
        _create_index_if_missing(name, table, columns)

    _enable_company_rls("remote_training_program_sectors")
    _enable_company_rls("remote_training_assignment_sectors")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("remote_training_assignment_sectors", "remote_training_program_sectors"):
        if inspector.has_table(table):
            _drop_company_rls(table)
            op.drop_table(table)

    for index_name, table in (
        ("ix_remote_program_questions_sector_code", "remote_training_program_questions"),
        ("ix_remote_training_questions_sector_code", "remote_training_questions"),
        ("ix_remote_training_sections_sector_code", "remote_training_sections"),
    ):
        _drop_index_if_exists(index_name, table)

    for table, column_name in (
        ("remote_training_program_questions", "sector_code"),
        ("remote_training_questions", "sector_code"),
        ("remote_training_sections", "sector_code"),
    ):
        inspector = sa.inspect(bind)
        if inspector.has_table(table) and column_name in {item["name"] for item in inspector.get_columns(table)}:
            op.drop_column(table, column_name)
