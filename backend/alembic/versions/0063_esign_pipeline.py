"""OSGB e-imza hattı: tek kullanımlık talep + imza artefaktı.

Revision ID: 0063
Revises: 0062
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0063"
down_revision: Union[str, None] = "0062"
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

    if not insp.has_table("e_sign_requests"):
        op.create_table(
            "e_sign_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("approval_id", sa.Integer(), sa.ForeignKey("document_approvals.id"), nullable=True),
            sa.Column("document_title", sa.String(220), nullable=False),
            sa.Column("document_kind", sa.String(80), nullable=False, server_default="genel"),
            sa.Column("source_sha256", sa.String(64), nullable=False),
            sa.Column("source_storage_path", sa.String(500), nullable=False),
            sa.Column("source_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("one_time_token", sa.String(64), nullable=False, unique=True),
            sa.Column("token_expires_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("consumed_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        op.create_index("ix_e_sign_requests_token", "e_sign_requests", ["one_time_token"], unique=True)

    if not insp.has_table("e_sign_artifacts"):
        op.create_table(
            "e_sign_artifacts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("e_sign_requests.id"), nullable=False, unique=True),
            sa.Column("approval_id", sa.Integer(), sa.ForeignKey("document_approvals.id"), nullable=True),
            sa.Column("signed_sha256", sa.String(64), nullable=False),
            sa.Column("signed_storage_path", sa.String(500), nullable=False),
            sa.Column("signed_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("signer_cn", sa.String(220), nullable=True),
            sa.Column("signer_subject", sa.String(500), nullable=True),
            sa.Column("cert_serial", sa.String(120), nullable=True),
            sa.Column("cert_sha256", sa.String(64), nullable=True),
            sa.Column("sign_mode", sa.String(40), nullable=True),
            sa.Column("agent_signature_id", sa.String(64), nullable=True),
            sa.Column("verification_status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("ocsp_status", sa.String(40), nullable=True),
            sa.Column("crl_status", sa.String(40), nullable=True),
            sa.Column("timestamp_status", sa.String(40), nullable=True),
            sa.Column("timestamp_token", sa.Text(), nullable=True),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("qualified_claim", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("audit_json", sa.Text(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )

    dialect = bind.dialect.name
    if dialect == "postgresql":
        _enable_company_rls("e_sign_requests", "e_sign_requests_company_isolation")
        _enable_company_rls("e_sign_artifacts", "e_sign_artifacts_company_isolation")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("e_sign_artifacts"):
        op.drop_table("e_sign_artifacts")
    if insp.has_table("e_sign_requests"):
        op.drop_table("e_sign_requests")
