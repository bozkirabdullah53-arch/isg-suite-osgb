"""Immutable training NACE classification snapshots.

Revision ID: 0078_training_nace
Revises: 0077_committee_approval
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0078_training_nace"
down_revision: Union[str, None] = "0077_committee_approval"
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
    if not insp.has_table("training_nace_snapshots"):
        op.create_table(
            "training_nace_snapshots",
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
            sa.Column("catalog_key", sa.String(140), nullable=True),
            sa.Column("nace_code", sa.String(20), nullable=True),
            sa.Column("nace_description", sa.String(500), nullable=True),
            sa.Column("nace_section_code", sa.String(4), nullable=True),
            sa.Column("nace_section_name", sa.String(220), nullable=True),
            sa.Column("subsector_code", sa.String(20), nullable=True),
            sa.Column("activity_group_code", sa.String(20), nullable=True),
            sa.Column("content_profile_code", sa.String(140), nullable=True),
            sa.Column("content_profile_name", sa.String(300), nullable=True),
            sa.Column("hazard_class", sa.String(40), nullable=True),
            sa.Column("training_topics_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("technical_risk_tags_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("special_risks_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("required_duration_minutes", sa.Integer(), nullable=True),
            sa.Column("required_duration_hours", sa.Integer(), nullable=True),
            sa.Column(
                "classification_status",
                sa.String(40),
                nullable=False,
                server_default="legacy_unverified",
            ),
            sa.Column("catalog_version", sa.String(80), nullable=False),
            sa.Column("catalog_hash", sa.String(64), nullable=False),
            sa.Column("source_snapshot_json", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint(
                "training_id", name="uq_training_nace_snapshot_training"
            ),
        )
        op.create_index(
            "ix_training_nace_snapshots_training_id",
            "training_nace_snapshots",
            ["training_id"],
        )
        op.create_index(
            "ix_training_nace_snapshots_company_id",
            "training_nace_snapshots",
            ["company_id"],
        )
        op.create_index(
            "ix_training_nace_snapshots_branch_id",
            "training_nace_snapshots",
            ["branch_id"],
        )
        op.create_index(
            "ix_training_nace_snapshots_catalog_key",
            "training_nace_snapshots",
            ["catalog_key"],
        )
        op.create_index(
            "ix_training_nace_snapshots_nace_code",
            "training_nace_snapshots",
            ["nace_code"],
        )
        op.create_index(
            "ix_training_nace_snapshots_profile",
            "training_nace_snapshots",
            ["content_profile_code"],
        )
        op.create_index(
            "ix_training_nace_snapshots_status",
            "training_nace_snapshots",
            ["classification_status"],
        )
        op.create_index(
            "ix_training_nace_snapshots_hash",
            "training_nace_snapshots",
            ["catalog_hash"],
        )
        op.create_index(
            "ix_training_nace_snapshots_created_at",
            "training_nace_snapshots",
            ["created_at"],
        )

    _enable_company_rls(
        "training_nace_snapshots",
        "training_nace_snapshots_company_scope",
    )


def downgrade() -> None:
    # Historical classification evidence is intentionally retained. Corrective
    # schema changes must be forward migrations; snapshots are not dropped.
    pass
