"""Nitelikli e-imza orkestrasyon tabloları (Desktop v0.10 birleşimi).

Revision ID: 0064
Revises: 0063

Not: 0063 (e_sign_requests/artifacts) korunur. Bu migration ek tablolar ekler;
mevcut belge onay / lokal agent hattını değiştirmez.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0064"
down_revision: Union[str, None] = "0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _company_scope_expr(table: str) -> str:
    return f"""
                  COALESCE(current_setting('app.current_user_id', true), '') = ''
                  OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                  OR (
                    COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                    AND {table}.company_id = ANY (
                      string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                    )
                  )
    """


def _enable_company_rls(table: str, policy: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    scope = _company_scope_expr(table)
    op.execute(
        sa.text(
            f"""
            DO $policy$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = current_schema()
                  AND tablename = '{table}'
                  AND policyname = '{policy}'
              ) THEN
                CREATE POLICY {policy} ON {table}
                  FOR ALL
                  USING ({scope})
                  WITH CHECK ({scope});
              END IF;
            END
            $policy$;
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("e_signature_requests"):
        op.create_table(
            "e_signature_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("document_records.id"), nullable=True),
            sa.Column("document_title", sa.String(220), nullable=False),
            sa.Column("document_kind", sa.String(80), nullable=False, server_default="general"),
            sa.Column("document_version", sa.String(30), nullable=False, server_default="1"),
            sa.Column("document_sha256", sa.String(64), nullable=False),
            sa.Column("signing_format", sa.String(30), nullable=False, server_default="PAdES"),
            sa.Column("required_signer_name", sa.String(160), nullable=False),
            sa.Column("required_signer_role", sa.String(100), nullable=False),
            sa.Column("signing_order", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
            sa.Column("nonce_hash", sa.String(64), nullable=True),
            sa.Column("nonce_expires_at", sa.DateTime(), nullable=True),
            sa.Column("certificate_subject", sa.String(500), nullable=True),
            sa.Column("certificate_serial", sa.String(160), nullable=True),
            sa.Column("certificate_issuer", sa.String(500), nullable=True),
            sa.Column("certificate_valid_from", sa.DateTime(), nullable=True),
            sa.Column("certificate_valid_to", sa.DateTime(), nullable=True),
            sa.Column("certificate_qualified", sa.Boolean(), nullable=True),
            sa.Column("revocation_status", sa.String(40), nullable=True),
            sa.Column("timestamp_status", sa.String(40), nullable=True),
            sa.Column("signature_value", sa.Text(), nullable=True),
            sa.Column("signed_document_sha256", sa.String(64), nullable=True),
            sa.Column("signed_at", sa.DateTime(), nullable=True),
            sa.Column("verification_status", sa.String(40), nullable=False, server_default="not_verified"),
            sa.Column("failure_reason", sa.String(1500), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_esign_company_status", "e_signature_requests", ["company_id", "status"])
        op.create_index("ix_esign_document_hash", "e_signature_requests", ["document_sha256"])

    if not insp.has_table("e_signature_audit_events"):
        op.create_table(
            "e_signature_audit_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("e_signature_requests.id"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("event_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("detail_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_esign_audit_request", "e_signature_audit_events", ["request_id", "created_at"])

    if bind.dialect.name == "postgresql":
        _enable_company_rls("e_signature_requests", "e_signature_requests_company_isolation")
        _enable_company_rls("e_signature_audit_events", "e_signature_audit_events_company_isolation")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("e_signature_audit_events"):
        op.drop_table("e_signature_audit_events")
    if insp.has_table("e_signature_requests"):
        op.drop_table("e_signature_requests")
