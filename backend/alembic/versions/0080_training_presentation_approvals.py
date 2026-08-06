"""Immutable NACE training presentation approval audit records.

Revision ID: 0080_presentation_approvals
Revises: 0079_training_presentation
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0080_presentation_approvals"
down_revision: Union[str, None] = "0079_training_presentation"
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
    table = "training_presentation_approvals"
    if not sa.inspect(bind).has_table(table):
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "presentation_version_id",
                sa.Integer(),
                sa.ForeignKey("training_presentation_versions.id", ondelete="CASCADE"),
                nullable=False,
            ),
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
            sa.Column("approval_method", sa.String(32), nullable=False),
            sa.Column("manifest_hash", sa.String(64), nullable=False),
            sa.Column("pptx_file_hash", sa.String(64), nullable=False),
            sa.Column("pdf_file_hash", sa.String(64), nullable=False),
            sa.Column(
                "approver_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("approver_name", sa.String(180), nullable=False),
            sa.Column("approver_role", sa.String(80), nullable=False),
            sa.Column("approval_note", sa.String(2000), nullable=True),
            sa.Column(
                "esign_request_id",
                sa.Integer(),
                sa.ForeignKey("e_signature_requests.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("esign_document_hash", sa.String(64), nullable=True),
            sa.Column("esign_signed_document_hash", sa.String(64), nullable=True),
            sa.Column("esign_verification_status", sa.String(40), nullable=True),
            sa.Column("esign_certificate_serial", sa.String(160), nullable=True),
            sa.Column("esign_evidence_json", sa.Text(), nullable=True),
            sa.Column("legal_notice", sa.String(700), nullable=False),
            sa.Column("event_hash", sa.String(64), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint(
                "presentation_version_id",
                name="uq_training_presentation_approval_version",
            ),
            sa.UniqueConstraint(
                "event_hash",
                name="uq_training_presentation_approval_event_hash",
            ),
            sa.CheckConstraint(
                "approval_method IN ('application_approval','qualified_esign')",
                name="ck_training_presentation_approval_method",
            ),
        )
        for index_name, columns in (
            ("ix_training_presentation_approval_training", ["training_id"]),
            ("ix_training_presentation_approval_company", ["company_id"]),
            ("ix_training_presentation_approval_version", ["presentation_version_id"]),
            ("ix_training_presentation_approval_created_at", ["created_at"]),
        ):
            op.create_index(index_name, table, columns)

    _enable_company_rls(
        table,
        "training_presentation_approvals_company_scope",
    )


def downgrade() -> None:
    table = "training_presentation_approvals"
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return
    if bind.dialect.name == "postgresql":
        op.execute(
            'DROP POLICY IF EXISTS "training_presentation_approvals_company_scope" '
            'ON "training_presentation_approvals"'
        )
    op.drop_table(table)
