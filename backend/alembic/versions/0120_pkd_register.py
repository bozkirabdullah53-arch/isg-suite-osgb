"""Add workplace/process based PKD register.
Revision ID: 0120_pkd_register
Revises: 0119_company_visit_qr_policy
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0120_pkd_register"
down_revision: Union[str, None] = "0119_company_visit_qr_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "explosion_protection_documents" in inspector.get_table_names():
        return

    op.create_table(
        "explosion_protection_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("document_no", sa.String(80), nullable=False),
        sa.Column("area_name", sa.String(220), nullable=False),
        sa.Column("process_name", sa.String(220), nullable=True),
        sa.Column("atmosphere_type", sa.String(40), nullable=False, server_default="gas_vapour_mist"),
        sa.Column("hazardous_materials", sa.String(1200), nullable=True),
        sa.Column("zone_classifications_json", sa.String(1200), nullable=True),
        sa.Column("ignition_sources_json", sa.String(1600), nullable=True),
        sa.Column("control_measures_json", sa.String(2400), nullable=True),
        sa.Column("responsible_person", sa.String(160), nullable=True),
        sa.Column("prepared_by", sa.String(160), nullable=True),
        sa.Column("approved_by", sa.String(160), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column("revision_no", sa.String(30), nullable=True),
        sa.Column("next_review_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("has_pkd_file", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(3000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_explosion_protection_documents_company_id", "explosion_protection_documents", ["company_id"])
    op.create_index("ix_explosion_protection_documents_branch_id", "explosion_protection_documents", ["branch_id"])
    op.create_index("ix_explosion_protection_documents_document_no", "explosion_protection_documents", ["document_no"])
    op.create_index("ix_explosion_protection_documents_area_name", "explosion_protection_documents", ["area_name"])
    op.create_index("ix_explosion_protection_documents_next_review_date", "explosion_protection_documents", ["next_review_date"])
    op.create_index("ix_explosion_protection_documents_status", "explosion_protection_documents", ["status"])
    op.create_index("ix_explosion_protection_documents_document_id", "explosion_protection_documents", ["document_id"])
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE explosion_protection_documents ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE explosion_protection_documents FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                """
                DO $policy$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = current_schema()
                      AND tablename = 'explosion_protection_documents'
                      AND policyname = 'explosion_protection_documents_company_scope'
                  ) THEN
                    CREATE POLICY explosion_protection_documents_company_scope
                      ON explosion_protection_documents
                      FOR ALL
                      USING (
                        COALESCE(current_setting('app.current_user_id', true), '') = ''
                        OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                        OR (
                          COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                          AND explosion_protection_documents.company_id = ANY (
                            string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                          )
                        )
                      )
                      WITH CHECK (
                        COALESCE(current_setting('app.current_user_id', true), '') = ''
                        OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                        OR (
                          COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                          AND explosion_protection_documents.company_id = ANY (
                            string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                          )
                        )
                      );
                  END IF;
                END
                $policy$;
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "explosion_protection_documents" in inspector.get_table_names():
        if bind.dialect.name == "postgresql":
            op.execute(
                sa.text(
                    "DROP POLICY IF EXISTS explosion_protection_documents_company_scope "
                    "ON explosion_protection_documents"
                )
            )
            op.execute(sa.text("ALTER TABLE explosion_protection_documents NO FORCE ROW LEVEL SECURITY"))
            op.execute(sa.text("ALTER TABLE explosion_protection_documents DISABLE ROW LEVEL SECURITY"))
        op.drop_table("explosion_protection_documents")
