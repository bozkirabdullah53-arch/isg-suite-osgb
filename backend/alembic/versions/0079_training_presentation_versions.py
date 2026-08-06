"""Versioned NACE training presentation snapshots.

Revision ID: 0079_training_presentation
Revises: 0078_training_nace
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0079_training_presentation"
down_revision: Union[str, None] = "0078_training_nace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_company_rls(table: str, policy: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    unset = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
    bypass = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
    allowed = (
        "string_to_array("
        "COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), ','"
        ")::integer[]"
    )
    scope = f"({unset}) OR ({bypass}) OR (company_id = ANY ({allowed}))"
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"')
    op.execute(
        f'CREATE POLICY "{policy}" ON "{table}" '
        f"FOR ALL USING ({scope}) WITH CHECK ({scope})"
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table = "training_presentation_versions"
    if not insp.has_table(table):
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "training_id",
                sa.Integer(),
                sa.ForeignKey("training_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "company_id",
                sa.Integer(),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "branch_id",
                sa.Integer(),
                sa.ForeignKey("branches.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "nace_snapshot_id",
                sa.Integer(),
                sa.ForeignKey("training_nace_snapshots.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
            sa.Column("contract_version", sa.String(120), nullable=False),
            sa.Column("contract_hash", sa.String(64), nullable=False),
            sa.Column("template_version", sa.String(120), nullable=False),
            sa.Column("manifest_version", sa.String(120), nullable=False),
            sa.Column("manifest_json", sa.Text(), nullable=False),
            sa.Column("manifest_hash", sa.String(64), nullable=False),
            sa.Column("catalog_key", sa.String(140), nullable=False),
            sa.Column("nace_code", sa.String(20), nullable=False),
            sa.Column("nace_description", sa.String(500), nullable=False),
            sa.Column("hazard_class", sa.String(40), nullable=False),
            sa.Column("content_profile_code", sa.String(140), nullable=False),
            sa.Column("catalog_version", sa.String(80), nullable=False),
            sa.Column("catalog_hash", sa.String(64), nullable=False),
            sa.Column("source_snapshot_json", sa.Text(), nullable=False),
            sa.Column("training_topics_json", sa.Text(), nullable=False),
            sa.Column("technical_risk_tags_json", sa.Text(), nullable=False),
            sa.Column("special_risks_json", sa.Text(), nullable=False),
            sa.Column(
                "output_formats_json",
                sa.Text(),
                nullable=False,
                server_default='["pptx","pdf"]',
            ),
            sa.Column(
                "primary_output_format",
                sa.String(16),
                nullable=False,
                server_default="pptx",
            ),
            sa.Column("pptx_storage_key", sa.String(700), nullable=True),
            sa.Column("pptx_file_hash", sa.String(64), nullable=True),
            sa.Column("pptx_file_size", sa.BigInteger(), nullable=True),
            sa.Column("pptx_content_type", sa.String(120), nullable=True),
            sa.Column("pdf_storage_key", sa.String(700), nullable=True),
            sa.Column("pdf_file_hash", sa.String(64), nullable=True),
            sa.Column("pdf_file_size", sa.BigInteger(), nullable=True),
            sa.Column("pdf_content_type", sa.String(120), nullable=True),
            sa.Column(
                "created_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "approved_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("failure_code", sa.String(80), nullable=True),
            sa.Column("failure_detail", sa.String(2000), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("generated_at", sa.DateTime(), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("failed_at", sa.DateTime(), nullable=True),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "training_id",
                "version",
                name="uq_training_presentation_training_version",
            ),
            sa.CheckConstraint(
                "version > 0",
                name="ck_training_presentation_version_positive",
            ),
            sa.CheckConstraint(
                "status IN ('draft','generated','approved','failed','archived')",
                name="ck_training_presentation_status",
            ),
        )
        for index_name, columns in (
            ("ix_training_presentation_training_id", ["training_id"]),
            ("ix_training_presentation_company_id", ["company_id"]),
            ("ix_training_presentation_branch_id", ["branch_id"]),
            ("ix_training_presentation_status", ["status"]),
            ("ix_training_presentation_manifest_hash", ["manifest_hash"]),
            ("ix_training_presentation_catalog_hash", ["catalog_hash"]),
            ("ix_training_presentation_created_at", ["created_at"]),
        ):
            op.create_index(index_name, table, columns)

    _enable_company_rls(
        table,
        "training_presentation_versions_company_scope",
    )


def downgrade() -> None:
    table = "training_presentation_versions"
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return
    if bind.dialect.name == "postgresql":
        op.execute(
            'DROP POLICY IF EXISTS "training_presentation_versions_company_scope" '
            'ON "training_presentation_versions"'
        )
    op.drop_table(table)
