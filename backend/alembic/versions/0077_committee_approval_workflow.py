"""Committee approval workflow, versioning and safe member removal metadata.

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


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("ohs_committee_members") or not insp.has_table("ohs_committee_meetings"):
        return

    member_cols = _columns(insp, "ohs_committee_members")
    member_additions = (
        ("removed_at", sa.Column("removed_at", sa.DateTime(), nullable=True)),
        ("removed_by_id", sa.Column("removed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True)),
        ("removal_reason_code", sa.Column("removal_reason_code", sa.String(60), nullable=True)),
        ("removal_reason_text", sa.Column("removal_reason_text", sa.String(1000), nullable=True)),
        ("removal_document_version", sa.Column("removal_document_version", sa.Integer(), nullable=True)),
    )
    for name, column in member_additions:
        if name not in member_cols:
            op.add_column("ohs_committee_members", column)

    meeting_cols = _columns(insp, "ohs_committee_meetings")
    meeting_additions = (
        ("approval_workflow_id", sa.Column("approval_workflow_id", sa.Integer(), sa.ForeignKey("eyas_workflows.id"), nullable=True)),
        ("approval_status", sa.Column("approval_status", sa.String(50), nullable=False, server_default="draft")),
        ("approval_current_step", sa.Column("approval_current_step", sa.Integer(), nullable=True)),
        ("document_version", sa.Column("document_version", sa.Integer(), nullable=False, server_default="1")),
        ("approval_submitted_at", sa.Column("approval_submitted_at", sa.DateTime(), nullable=True)),
        ("approval_completed_at", sa.Column("approval_completed_at", sa.DateTime(), nullable=True)),
        ("approval_invalidated_at", sa.Column("approval_invalidated_at", sa.DateTime(), nullable=True)),
        ("updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True)),
    )
    for name, column in meeting_additions:
        if name not in meeting_cols:
            op.add_column("ohs_committee_meetings", column)

    indexes = {i["name"] for i in insp.get_indexes("ohs_committee_meetings")}
    if "ix_ohs_committee_meetings_workflow" not in indexes:
        op.create_index("ix_ohs_committee_meetings_workflow", "ohs_committee_meetings", ["approval_workflow_id"])
    if "ix_ohs_committee_meetings_approval_status" not in indexes:
        op.create_index("ix_ohs_committee_meetings_approval_status", "ohs_committee_meetings", ["company_id", "approval_status"])


def downgrade() -> None:
    # Additive audit/version columns are intentionally retained to avoid losing
    # historical approval and membership-removal evidence.
    pass
