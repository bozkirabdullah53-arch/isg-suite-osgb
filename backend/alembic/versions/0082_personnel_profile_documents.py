"""Private object-store versions for ordinary personnel profile documents.

Revision ID: 0082_personnel_profile_documents
Revises: 0081_personnel_profile_core
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0082_personnel_profile_documents"
down_revision: Union[str, None] = "0081_personnel_profile_core"
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
    inspector = sa.inspect(bind)
    table = "personnel_profile_documents"
    if not inspector.has_table(table):
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "profile_id",
                sa.Integer(),
                sa.ForeignKey("personnel_profiles.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "company_id",
                sa.Integer(),
                sa.ForeignKey("companies.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("document_key", sa.String(36), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column(
                "supersedes_id",
                sa.Integer(),
                sa.ForeignKey("personnel_profile_documents.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column("idempotency_key", sa.String(80), nullable=False),
            sa.Column("document_kind", sa.String(32), nullable=False),
            sa.Column("category", sa.String(64), nullable=False),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("document_number", sa.String(120), nullable=True),
            sa.Column("issuing_organization", sa.String(220), nullable=True),
            sa.Column("issue_date", sa.Date(), nullable=True),
            sa.Column("valid_from", sa.Date(), nullable=True),
            sa.Column("expiration_date", sa.Date(), nullable=True),
            sa.Column(
                "no_expiration",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("object_key", sa.String(500), nullable=False),
            sa.Column("mime_type", sa.String(120), nullable=False),
            sa.Column("file_extension", sa.String(16), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("checksum_sha256", sa.String(64), nullable=False),
            sa.Column(
                "access_classification",
                sa.String(32),
                nullable=False,
                server_default="internal_only",
            ),
            sa.Column(
                "processing_purpose",
                sa.String(120),
                nullable=False,
                server_default="professional_profile_management",
            ),
            sa.Column(
                "retention_policy",
                sa.String(120),
                nullable=False,
                server_default="personnel_profile_ordinary_v1",
            ),
            sa.Column(
                "verification_status",
                sa.String(24),
                nullable=False,
                server_default="unverified",
            ),
            sa.Column(
                "lifecycle_status",
                sa.String(24),
                nullable=False,
                server_default="active",
            ),
            sa.Column("change_reason", sa.String(500), nullable=True),
            sa.Column(
                "created_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "verified_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("verified_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint(
                "profile_id",
                "document_key",
                "version",
                name="uq_personnel_profile_document_version",
            ),
            sa.UniqueConstraint(
                "profile_id",
                "idempotency_key",
                name="uq_personnel_profile_document_idempotency",
            ),
            sa.CheckConstraint(
                "version > 0",
                name="ck_personnel_profile_document_version_positive",
            ),
            sa.CheckConstraint(
                "document_kind IN ('profile_photo','cv','qualification','certificate')",
                name="ck_personnel_profile_document_kind",
            ),
            sa.CheckConstraint(
                "category IN ("
                "'profile_photo','cv','diploma','graduation_certificate',"
                "'occupational_safety_certificate','workplace_physician_certificate',"
                "'other_health_personnel_certificate','trainer_certificate',"
                "'myk_certificate','mastership_certificate','journeyman_certificate',"
                "'operator_certificate','first_aid_certificate',"
                "'working_at_height_certificate','fire_safety_certificate',"
                "'emergency_response_certificate','explosion_protection_certificate',"
                "'risk_assessment_certificate','electrical_work_certificate',"
                "'scaffolding_certificate','welding_certificate','hygiene_certificate',"
                "'language_certificate','other_professional_document'"
                ")",
                name="ck_personnel_profile_document_category",
            ),
            sa.CheckConstraint(
                "access_classification IN ('internal_only','cv_eligible','share_eligible')",
                name="ck_personnel_profile_document_access",
            ),
            sa.CheckConstraint(
                "verification_status IN ('unverified','verified','rejected')",
                name="ck_personnel_profile_document_verification",
            ),
            sa.CheckConstraint(
                "lifecycle_status IN ('active','archived')",
                name="ck_personnel_profile_document_lifecycle",
            ),
        )
        for index_name, columns in (
            ("ix_personnel_profile_document_profile", ["profile_id"]),
            ("ix_personnel_profile_document_company", ["company_id"]),
            ("ix_personnel_profile_document_key", ["document_key"]),
            ("ix_personnel_profile_document_kind", ["document_kind"]),
            ("ix_personnel_profile_document_category", ["category"]),
            ("ix_personnel_profile_document_expiration", ["expiration_date"]),
            ("ix_personnel_profile_document_created_at", ["created_at"]),
        ):
            op.create_index(index_name, table, columns)

    _enable_company_rls(
        table,
        "personnel_profile_documents_company_scope",
    )


def downgrade() -> None:
    bind = op.get_bind()
    table = "personnel_profile_documents"
    if not sa.inspect(bind).has_table(table):
        return
    if bind.dialect.name == "postgresql":
        op.execute(
            'DROP POLICY IF EXISTS "personnel_profile_documents_company_scope" '
            'ON "personnel_profile_documents"'
        )
    op.drop_table(table)
