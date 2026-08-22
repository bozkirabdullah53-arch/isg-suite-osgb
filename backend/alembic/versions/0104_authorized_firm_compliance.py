"""Add tenant-scoped authorized firm and compliance records."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0104_authorized_firm_compliance"
down_revision: Union[str, None] = "0103_field_inspection_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _company_scope() -> str:
    unset = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
    bypass = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
    allowed = (
        "string_to_array(COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), ',')::integer[]"
    )
    return f"({unset}) OR ({bypass}) OR (company_id = ANY ({allowed}))"


def _osgb_scope() -> str:
    unset = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
    bypass = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
    current_osgb = "NULLIF(current_setting('app.current_osgb_id', true), '')::integer"
    return f"({unset}) OR ({bypass}) OR (osgb_id = {current_osgb})"


def _install_policy(table: str, policy: str, scope: str) -> None:
    if op.get_bind().dialect.name != "postgresql" or not _has_table(table):
        return
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"')
    op.execute(
        f'CREATE POLICY "{policy}" ON "{table}" '
        f"FOR ALL USING ({scope}) WITH CHECK ({scope})"
    )


def upgrade() -> None:
    if not _has_table("authorized_firm_profiles"):
        op.create_table(
            "authorized_firm_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("firm_name", sa.String(220), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("firm_type", sa.String(80), nullable=True),
            sa.Column("province", sa.String(80), nullable=True),
            sa.Column("district", sa.String(100), nullable=True),
            sa.Column("address", sa.String(500), nullable=True),
            sa.Column("authorized_representative", sa.String(160), nullable=True),
            sa.Column("contact_email", sa.String(255), nullable=True),
            sa.Column("contact_phone", sa.String(40), nullable=True),
            sa.Column("employee_count_declared", sa.Integer(), nullable=True),
            sa.Column("hazard_class", sa.String(40), nullable=True),
            sa.Column("authorization_scope", sa.String(2000), nullable=True),
            sa.Column("authorization_number", sa.String(100), nullable=True),
            sa.Column("authorization_issue_date", sa.Date(), nullable=True),
            sa.Column("authorization_start_date", sa.Date(), nullable=True),
            sa.Column("authorization_expiry_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.String(4000), nullable=True),
            sa.Column("last_review_date", sa.Date(), nullable=True),
            sa.Column("review_state", sa.String(24), nullable=False, server_default="internal_record"),
            sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("onboarding_current_step", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("onboarding_completed_steps", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("onboarding_status", sa.String(24), nullable=False, server_default="draft"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("company_id", name="uq_authorized_firm_company"),
            sa.CheckConstraint(
                "authorization_expiry_date IS NULL OR authorization_start_date IS NULL OR authorization_expiry_date >= authorization_start_date",
                name="ck_authorized_firm_authorization_period",
            ),
            sa.CheckConstraint(
                "authorization_expiry_date IS NULL OR authorization_issue_date IS NULL OR authorization_expiry_date >= authorization_issue_date",
                name="ck_authorized_firm_issue_expiry",
            ),
            sa.CheckConstraint("review_state IN ('internal_record','manually_reviewed')", name="ck_authorized_firm_review_state"),
            sa.CheckConstraint("onboarding_status IN ('draft','in_progress','completed')", name="ck_authorized_firm_onboarding_status"),
            sa.CheckConstraint("onboarding_current_step >= 1 AND onboarding_current_step <= 11", name="ck_authorized_firm_onboarding_step"),
        )
        op.create_index("ix_authorized_firm_osgb", "authorized_firm_profiles", ["osgb_id"])
        op.create_index("ix_authorized_firm_company", "authorized_firm_profiles", ["company_id"])
        op.create_index("ix_authorized_firm_location", "authorized_firm_profiles", ["province", "district"])
        op.create_index("ix_authorized_firm_expiry", "authorized_firm_profiles", ["authorization_expiry_date"])
        op.create_index("ix_authorized_firm_active", "authorized_firm_profiles", ["is_active"])

    if not _has_table("authorized_firm_documents"):
        op.create_table(
            "authorized_firm_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("authorized_firm_profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_record_id", sa.Integer(), sa.ForeignKey("document_records.id", ondelete="SET NULL"), nullable=True),
            sa.Column("document_type", sa.String(80), nullable=False),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("mandatory", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("expiry_date", sa.Date(), nullable=True),
            sa.Column("review_date", sa.Date(), nullable=True),
            sa.Column("renewal_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("expiry_date IS NULL OR start_date IS NULL OR expiry_date >= start_date", name="ck_authorized_firm_document_period"),
            sa.CheckConstraint("renewal_date IS NULL OR review_date IS NULL OR renewal_date >= review_date", name="ck_authorized_firm_document_review_period"),
        )
        op.create_index("ix_authorized_firm_document_profile", "authorized_firm_documents", ["profile_id"])
        op.create_index("ix_authorized_firm_document_company", "authorized_firm_documents", ["company_id"])
        op.create_index("ix_authorized_firm_document_osgb", "authorized_firm_documents", ["osgb_id"])
        op.create_index("ix_authorized_firm_document_expiry", "authorized_firm_documents", ["expiry_date"])

    if not _has_table("professional_compliance_profiles"):
        op.create_table(
            "professional_compliance_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("professional_id", sa.Integer(), sa.ForeignKey("isg_professionals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("certificate_issue_date", sa.Date(), nullable=True),
            sa.Column("certificate_expiry_date", sa.Date(), nullable=True),
            sa.Column("document_review_date", sa.Date(), nullable=True),
            sa.Column("document_renewal_date", sa.Date(), nullable=True),
            sa.Column("required_documents_status", sa.String(24), nullable=False, server_default="review_required"),
            sa.Column("required_documents_note", sa.String(2000), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("professional_id", name="uq_professional_compliance_professional"),
            sa.CheckConstraint("certificate_expiry_date IS NULL OR certificate_issue_date IS NULL OR certificate_expiry_date >= certificate_issue_date", name="ck_professional_compliance_certificate_period"),
            sa.CheckConstraint("document_renewal_date IS NULL OR document_review_date IS NULL OR document_renewal_date >= document_review_date", name="ck_professional_compliance_review_period"),
            sa.CheckConstraint("required_documents_status IN ('complete','incomplete','review_required')", name="ck_professional_required_documents_status"),
        )
        op.create_index("ix_professional_compliance_osgb", "professional_compliance_profiles", ["osgb_id"])
        op.create_index("ix_professional_compliance_expiry", "professional_compliance_profiles", ["certificate_expiry_date"])

    if not _has_table("compliance_score_snapshots"):
        op.create_table(
            "compliance_score_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("authorized_firm_profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("overall_score", sa.Integer(), nullable=False),
            sa.Column("quality_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(24), nullable=False),
            sa.Column("category_scores_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("quality_scores_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("blockers_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="ck_compliance_snapshot_overall_score"),
            sa.CheckConstraint("quality_score >= 0 AND quality_score <= 100", name="ck_compliance_snapshot_quality_score"),
        )
        op.create_index("ix_compliance_snapshot_profile", "compliance_score_snapshots", ["profile_id", "created_at"])
        op.create_index("ix_compliance_snapshot_company", "compliance_score_snapshots", ["company_id"])
        op.create_index("ix_compliance_snapshot_osgb", "compliance_score_snapshots", ["osgb_id"])

    company_scope = _company_scope()
    for table, policy in (
        ("authorized_firm_profiles", "authorized_firm_profiles_company_scope"),
        ("authorized_firm_documents", "authorized_firm_documents_company_scope"),
        ("compliance_score_snapshots", "compliance_score_snapshots_company_scope"),
    ):
        _install_policy(table, policy, company_scope)
    _install_policy(
        "professional_compliance_profiles",
        "professional_compliance_profiles_osgb_scope",
        _osgb_scope(),
    )


def downgrade() -> None:
    for table in (
        "compliance_score_snapshots",
        "professional_compliance_profiles",
        "authorized_firm_documents",
        "authorized_firm_profiles",
    ):
        if _has_table(table):
            op.drop_table(table)
