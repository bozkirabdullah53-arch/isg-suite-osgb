"""Committee approval, versioning, signatures and safe member removal metadata.

Revision ID: 0077_committee_approval
Revises: 0076_committee_professional
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0077_committee_approval"
down_revision: Union[str, None] = "0076_committee_professional"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(insp, table: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(table)}


def _add_missing_columns(table: str, existing: set[str], additions) -> None:
    for name, column in additions:
        if name not in existing:
            op.add_column(table, column)


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
        f'FOR ALL USING ({scope}) WITH CHECK ({scope})'
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("ohs_committee_members") or not insp.has_table("ohs_committee_meetings"):
        return

    _add_missing_columns(
        "ohs_committee_members",
        _columns(insp, "ohs_committee_members"),
        (
            ("removed_at", sa.Column("removed_at", sa.DateTime(), nullable=True)),
            ("removed_by_id", sa.Column("removed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True)),
            ("removal_reason_code", sa.Column("removal_reason_code", sa.String(60), nullable=True)),
            ("removal_reason_text", sa.Column("removal_reason_text", sa.String(1000), nullable=True)),
            ("removal_document_version", sa.Column("removal_document_version", sa.Integer(), nullable=True)),
        ),
    )

    _add_missing_columns(
        "ohs_committee_meetings",
        _columns(insp, "ohs_committee_meetings"),
        (
            ("approval_workflow_id", sa.Column("approval_workflow_id", sa.Integer(), sa.ForeignKey("eyas_workflows.id"), nullable=True)),
            ("approval_status", sa.Column("approval_status", sa.String(50), nullable=False, server_default="draft")),
            ("approval_current_step", sa.Column("approval_current_step", sa.Integer(), nullable=True)),
            ("document_version", sa.Column("document_version", sa.Integer(), nullable=False, server_default="1")),
            ("approval_submitted_at", sa.Column("approval_submitted_at", sa.DateTime(), nullable=True)),
            ("approval_completed_at", sa.Column("approval_completed_at", sa.DateTime(), nullable=True)),
            ("approval_invalidated_at", sa.Column("approval_invalidated_at", sa.DateTime(), nullable=True)),
            ("updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True)),
        ),
    )

    meeting_indexes = {i["name"] for i in sa.inspect(bind).get_indexes("ohs_committee_meetings")}
    if "ix_ohs_committee_meetings_workflow" not in meeting_indexes:
        op.create_index("ix_ohs_committee_meetings_workflow", "ohs_committee_meetings", ["approval_workflow_id"])
    if "ix_ohs_committee_meetings_approval_status" not in meeting_indexes:
        op.create_index("ix_ohs_committee_meetings_approval_status", "ohs_committee_meetings", ["company_id", "approval_status"])

    if not sa.inspect(bind).has_table("ohs_committee_signature_steps"):
        op.create_table(
            "ohs_committee_signature_steps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("ohs_committee_meetings.id"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("document_version", sa.Integer(), nullable=False),
            sa.Column("step_order", sa.Integer(), nullable=False),
            sa.Column("signer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("role_label", sa.String(120), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("esign_request_id", sa.Integer(), sa.ForeignKey("e_sign_requests.id"), nullable=True),
            sa.Column("esign_artifact_id", sa.Integer(), sa.ForeignKey("e_sign_artifacts.id"), nullable=True),
            sa.Column("signed_at", sa.DateTime(), nullable=True),
            sa.Column("invalidated_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("meeting_id", "document_version", "step_order", name="uq_committee_signature_version_step"),
        )
        op.create_index("ix_committee_signature_company_status", "ohs_committee_signature_steps", ["company_id", "status"])
        op.create_index("ix_committee_signature_signer_status", "ohs_committee_signature_steps", ["signer_user_id", "status"])
        op.create_index("ix_committee_signature_request", "ohs_committee_signature_steps", ["esign_request_id"], unique=True)

    if not sa.inspect(bind).has_table("ohs_committee_meeting_versions"):
        op.create_table(
            "ohs_committee_meeting_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("ohs_committee_meetings.id"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("document_version", sa.Integer(), nullable=False),
            sa.Column("meeting_snapshot_json", sa.Text(), nullable=False),
            sa.Column("member_snapshot_json", sa.Text(), nullable=True),
            sa.Column("approval_workflow_id", sa.Integer(), sa.ForeignKey("eyas_workflows.id"), nullable=True),
            sa.Column("final_signature_artifact_id", sa.Integer(), sa.ForeignKey("e_sign_artifacts.id"), nullable=True),
            sa.Column("pdf_sha256", sa.String(64), nullable=True),
            sa.Column("archive_reason", sa.String(120), nullable=False, server_default="material_change"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("meeting_id", "document_version", name="uq_committee_meeting_version"),
        )
        op.create_index("ix_committee_meeting_versions_company", "ohs_committee_meeting_versions", ["company_id", "meeting_id"])

    _enable_company_rls(
        "ohs_committee_signature_steps",
        "ohs_committee_signature_steps_company_scope",
    )
    _enable_company_rls(
        "ohs_committee_meeting_versions",
        "ohs_committee_meeting_versions_company_scope",
    )


def downgrade() -> None:
    # Audit/version/signature evidence is intentionally retained. A forward
    # migration must be used for schema correction; historical evidence is not
    # removed automatically.
    pass
