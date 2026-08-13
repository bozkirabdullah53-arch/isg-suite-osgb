"""Add a firm-independent central catalog for remote OHS packages.

The existing company-scoped remote training tables remain unchanged.  These
three additive tables hold reusable package definitions and uploaded video
revisions before a package is assigned to a company.

Revision ID: 0091_remote_ohs_catalog
Revises: 0090_remote_ohs_sector
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0091_remote_ohs_catalog"
down_revision: Union[str, None] = "0090_remote_ohs_sector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATALOG_TABLES = (
    "remote_training_catalog_videos",
    "remote_training_catalog_sections",
    "remote_training_catalog_packages",
)


def _enable_catalog_rls(table: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    policy = f"{table}_osgb_scope"
    unset = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
    bypass = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
    current_osgb = "NULLIF(current_setting('app.current_osgb_id', true), '')::integer"
    # NULL osgb_id is the intentionally shared/global catalog.  Company and
    # employee identifiers are never stored in these tables.
    scope = f"({unset}) OR ({bypass}) OR (osgb_id IS NULL) OR (osgb_id = {current_osgb})"
    if table != "remote_training_catalog_packages":
        scope = f"({unset}) OR ({bypass}) OR EXISTS (SELECT 1 FROM remote_training_catalog_packages p WHERE p.id = package_id AND (p.osgb_id IS NULL OR p.osgb_id = {current_osgb}))"
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{policy}" ON "{table}" '
            f"FOR ALL USING ({scope}) WITH CHECK ({scope})"
        )
    )


def _drop_catalog_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_osgb_scope" ON "{table}"'))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("remote_training_catalog_packages"):
        op.create_table(
            "remote_training_catalog_packages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL")),
            sa.Column("code", sa.String(96), nullable=False),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("training_type", sa.String(120), nullable=False, server_default="Basic Occupational Health and Safety Training"),
            sa.Column("total_duration_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("requires_final_exam", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("completion_threshold_percent", sa.Integer(), nullable=False, server_default="90"),
            sa.Column("passing_score", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("attempt_limit", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("archived_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("osgb_id", "code", name="uq_remote_catalog_package_scope_code"),
        )
        op.create_index("ix_remote_catalog_packages_osgb_id", "remote_training_catalog_packages", ["osgb_id"])
        op.create_index("ix_remote_catalog_packages_status", "remote_training_catalog_packages", ["status"])
        op.create_index("ix_remote_catalog_packages_scope_status", "remote_training_catalog_packages", ["osgb_id", "status"])

    if not inspector.has_table("remote_training_catalog_sections"):
        op.create_table(
            "remote_training_catalog_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("package_id", sa.Integer(), sa.ForeignKey("remote_training_catalog_packages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(24), nullable=False, server_default="active"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("package_id", "code", name="uq_remote_catalog_section_package_code"),
            sa.UniqueConstraint("package_id", "order_index", name="uq_remote_catalog_section_package_order"),
        )
        op.create_index("ix_remote_catalog_sections_package", "remote_training_catalog_sections", ["package_id"])

    if not inspector.has_table("remote_training_catalog_videos"):
        op.create_table(
            "remote_training_catalog_videos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("package_id", sa.Integer(), sa.ForeignKey("remote_training_catalog_packages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("remote_training_catalog_sections.id", ondelete="CASCADE"), nullable=False),
            sa.Column("revision_of_id", sa.Integer(), sa.ForeignKey("remote_training_catalog_videos.id", ondelete="SET NULL")),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("learning_objectives", sa.Text()),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(32), nullable=False, server_default="uploading"),
            sa.Column("original_file_name", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(120), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("width", sa.Integer()),
            sa.Column("height", sa.Integer()),
            sa.Column("codec", sa.String(80)),
            sa.Column("storage_key", sa.String(700), nullable=False, unique=True),
            sa.Column("processing_job_id", sa.String(80)),
            sa.Column("processing_error", sa.String(1000)),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("archived_at", sa.DateTime()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_remote_catalog_videos_package", "remote_training_catalog_videos", ["package_id"])
        op.create_index("ix_remote_catalog_videos_section", "remote_training_catalog_videos", ["section_id"])
        op.create_index("ix_remote_catalog_videos_revision_of_id", "remote_training_catalog_videos", ["revision_of_id"])
        op.create_index("ix_remote_catalog_videos_status", "remote_training_catalog_videos", ["status"])
        op.create_index("ix_remote_catalog_videos_processing_job_id", "remote_training_catalog_videos", ["processing_job_id"])
        op.create_index("ix_remote_catalog_videos_created_at", "remote_training_catalog_videos", ["created_at"])
        op.create_index("ix_remote_catalog_videos_current", "remote_training_catalog_videos", ["package_id", "is_current"])
        op.create_index("ix_remote_catalog_videos_package_status", "remote_training_catalog_videos", ["package_id", "status"])
        op.create_index("ix_remote_catalog_videos_section_order", "remote_training_catalog_videos", ["section_id", "order_index"])

    for table in reversed(CATALOG_TABLES):
        _enable_catalog_rls(table)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in CATALOG_TABLES:
        if inspector.has_table(table):
            _drop_catalog_rls(table)
    for table in CATALOG_TABLES:
        if inspector.has_table(table):
            op.drop_table(table)
