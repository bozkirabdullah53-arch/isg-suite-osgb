"""Eyas Digital Approval — sıralı dijital onay (QES değil).

Revision ID: 0065
Revises: 0064

Additive only. Mevcut document_approvals / esign / signer bozulmaz.
Downgrade tabloları düşürür; canlıda tercih FORCE_OFF + Render rollback.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0065"
down_revision: Union[str, None] = "0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 0001 mevcut model metadata'sını create_all ile kurduğu için yeni bir
    # veritabanında bu tablolar 0065'e gelmeden önce zaten bulunabilir.
    if not insp.has_table("eyas_workflows"):
        op.create_table(
            "eyas_workflows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("document_kind", sa.String(80), nullable=False, server_default="genel"),
            sa.Column("source_document_id", sa.Integer(), sa.ForeignKey("document_records.id"), nullable=True),
            sa.Column("source_sha256", sa.String(64), nullable=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="draft", index=True),
            sa.Column("current_step_order", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("legal_label", sa.String(80), nullable=False, server_default="digital_approval_not_qes"),
            sa.Column("qes_request_id", sa.Integer(), nullable=True),
            sa.Column("archive_path", sa.String(500), nullable=True),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    insp = sa.inspect(bind)
    if not insp.has_table("eyas_steps"):
        op.create_table(
            "eyas_steps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("eyas_workflows.id"), nullable=False, index=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("step_order", sa.Integer(), nullable=False),
            sa.Column("assignee_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("role_label", sa.String(100), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending", index=True),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("ip_address", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("device_note", sa.String(240), nullable=True),
            sa.Column("note", sa.String(1000), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    insp = sa.inspect(bind)
    step_indexes = {item["name"] for item in insp.get_indexes("eyas_steps")}
    if "ix_eyas_steps_wf_order" not in step_indexes:
        op.create_index("ix_eyas_steps_wf_order", "eyas_steps", ["workflow_id", "step_order"], unique=True)

    insp = sa.inspect(bind)
    if not insp.has_table("eyas_events"):
        op.create_table(
            "eyas_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("eyas_workflows.id"), nullable=False, index=True),
            sa.Column("step_id", sa.Integer(), sa.ForeignKey("eyas_steps.id"), nullable=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("action", sa.String(80), nullable=False, index=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("prev_hash", sa.String(64), nullable=True),
            sa.Column("event_hash", sa.String(64), nullable=False, unique=True, index=True),
            sa.Column("ip_address", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("eyas_events"):
        op.drop_table("eyas_events")

    insp = sa.inspect(bind)
    if insp.has_table("eyas_steps"):
        indexes = {item["name"] for item in insp.get_indexes("eyas_steps")}
        if "ix_eyas_steps_wf_order" in indexes:
            op.drop_index("ix_eyas_steps_wf_order", table_name="eyas_steps")
        op.drop_table("eyas_steps")

    if sa.inspect(bind).has_table("eyas_workflows"):
        op.drop_table("eyas_workflows")
