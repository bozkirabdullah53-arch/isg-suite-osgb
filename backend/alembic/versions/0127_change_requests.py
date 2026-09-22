"""İBYS Değişiklik Talebi tabloları (§3-§5).

Talep → doğrulama → onay → uygulama → kapatma akışını destekler.
Tümü nullable ve additive; mevcut veriler etkilenmez.

Revision ID: 0127
Revises: 0126
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0127"
down_revision: Union[str, None] = "0126"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "change_requests" not in tables:
        op.create_table(
            "change_requests",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("request_no", sa.String(32), nullable=False, unique=True, index=True),
            sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("requested_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("requester_type", sa.String(20), nullable=False, default="employer"),
            sa.Column("channel", sa.String(20), nullable=False, default="platform"),
            sa.Column("request_kind", sa.String(20), nullable=True),
            sa.Column("identity_verified", sa.Boolean, nullable=False, default=False),
            sa.Column("verification_method", sa.String(40), nullable=True),
            sa.Column("target_entity_type", sa.String(80), nullable=False, index=True),
            sa.Column("target_entity_id", sa.String(80), nullable=True),
            sa.Column("field_name", sa.String(80), nullable=True),
            sa.Column("old_value", sa.Text, nullable=True),
            sa.Column("requested_value", sa.Text, nullable=False),
            sa.Column("justification", sa.Text, nullable=False),
            sa.Column("attachment_path", sa.String(500), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, default="submitted", index=True),
            sa.Column("verified_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("verified_at", sa.DateTime, nullable=True),
            sa.Column("approved_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("approved_at", sa.DateTime, nullable=True),
            sa.Column("applied_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("applied_at", sa.DateTime, nullable=True),
            sa.Column("rejected_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("rejected_at", sa.DateTime, nullable=True),
            sa.Column("rejection_reason", sa.Text, nullable=True),
            sa.Column("sla_due_at", sa.DateTime, nullable=True, index=True),
            sa.Column("created_at", sa.DateTime, nullable=False, default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_change_requests_company_id", "change_requests", ["company_id"])
        op.create_index("ix_change_requests_status", "change_requests", ["status"])
        op.create_index("ix_change_requests_sla_due_at", "change_requests", ["sla_due_at"])

    if "change_request_events" not in tables:
        op.create_table(
            "change_request_events",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("change_request_id", sa.Integer, sa.ForeignKey("change_requests.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("from_status", sa.String(20), nullable=True),
            sa.Column("to_status", sa.String(20), nullable=False),
            sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("note", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, default=sa.func.now()),
        )
        op.create_index("ix_change_request_events_request_id", "change_request_events", ["change_request_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "change_request_events" in tables:
        op.drop_table("change_request_events")
    if "change_requests" in tables:
        op.drop_table("change_requests")