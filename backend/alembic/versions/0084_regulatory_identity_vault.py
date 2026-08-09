"""Isolated encrypted regulatory identity vault.

Revision ID: 0084_regulatory_identity_vault
Revises: 0083_profile_osgb_scope
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0084_regulatory_identity_vault"
down_revision: Union[str, None] = "0083_profile_osgb_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_company_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    unset = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
    bypass = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
    allowed = (
        "string_to_array(COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), ',')::integer[]"
    )
    scope = f"({unset}) OR ({bypass}) OR (company_id = ANY ({allowed}))"
    op.execute('ALTER TABLE "regulatory_identities" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "regulatory_identities" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS "regulatory_identities_company_scope" ON "regulatory_identities"')
    op.execute(
        'CREATE POLICY "regulatory_identities_company_scope" ON "regulatory_identities" '
        f"FOR ALL USING ({scope}) WITH CHECK ({scope})"
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("regulatory_identities"):
        return
    op.create_table(
        "regulatory_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identity_type", sa.String(20), nullable=False, server_default="tckn"),
        sa.Column("masked_value", sa.String(32), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("lookup_hash", sa.String(64), nullable=False),
        sa.Column("encryption_version", sa.String(24), nullable=False, server_default="rid:v1"),
        sa.Column("verified_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("employee_id", "identity_type", name="uq_regulatory_identity_employee_type"),
        sa.UniqueConstraint("company_id", "identity_type", "lookup_hash", name="uq_regulatory_identity_company_lookup"),
    )
    op.create_index("ix_regulatory_identity_company", "regulatory_identities", ["company_id"])
    op.create_index("ix_regulatory_identity_employee", "regulatory_identities", ["employee_id"])
    op.create_index("ix_regulatory_identity_lookup", "regulatory_identities", ["lookup_hash"])
    _enable_company_rls()


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("regulatory_identities"):
        return
    if bind.dialect.name == "postgresql":
        op.execute('DROP POLICY IF EXISTS "regulatory_identities_company_scope" ON "regulatory_identities"')
    op.drop_table("regulatory_identities")
