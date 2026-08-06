"""Isolated, company-scoped Digital Personnel Card core tables.

Revision ID: 0081_personnel_profile_core
Revises: 0080_presentation_approvals
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0081_personnel_profile_core"
down_revision: Union[str, None] = "0080_presentation_approvals"
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

    if not inspector.has_table("personnel_profiles"):
        op.create_table(
            "personnel_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "osgb_id",
                sa.Integer(),
                sa.ForeignKey("osgb_organizations.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "company_id",
                sa.Integer(),
                sa.ForeignKey("companies.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "branch_id",
                sa.Integer(),
                sa.ForeignKey("branches.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("subject_type", sa.String(24), nullable=False),
            sa.Column(
                "employee_id",
                sa.Integer(),
                sa.ForeignKey("employees.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column(
                "professional_id",
                sa.Integer(),
                sa.ForeignKey("isg_professionals.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("status", sa.String(24), nullable=False, server_default="active"),
            sa.Column(
                "created_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "archived_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "company_id",
                "employee_id",
                name="uq_personnel_profile_company_employee",
            ),
            sa.UniqueConstraint(
                "company_id",
                "professional_id",
                name="uq_personnel_profile_company_professional",
            ),
            sa.CheckConstraint(
                "(subject_type = 'employee' AND employee_id IS NOT NULL AND professional_id IS NULL) "
                "OR (subject_type = 'professional' AND professional_id IS NOT NULL AND employee_id IS NULL)",
                name="ck_personnel_profile_exact_subject",
            ),
            sa.CheckConstraint(
                "subject_type IN ('employee','professional')",
                name="ck_personnel_profile_subject_type",
            ),
            sa.CheckConstraint(
                "status IN ('active','archived')",
                name="ck_personnel_profile_status",
            ),
        )
        for index_name, columns in (
            ("ix_personnel_profile_osgb", ["osgb_id"]),
            ("ix_personnel_profile_company", ["company_id"]),
            ("ix_personnel_profile_branch", ["branch_id"]),
            ("ix_personnel_profile_employee", ["employee_id"]),
            ("ix_personnel_profile_professional", ["professional_id"]),
            ("ix_personnel_profile_user", ["user_id"]),
            ("ix_personnel_profile_status", ["status"]),
            ("ix_personnel_profile_created_at", ["created_at"]),
        ):
            op.create_index(index_name, "personnel_profiles", columns)

    if not inspector.has_table("personnel_profile_contacts"):
        op.create_table(
            "personnel_profile_contacts",
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
            sa.Column("entry_key", sa.String(36), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column(
                "supersedes_id",
                sa.Integer(),
                sa.ForeignKey("personnel_profile_contacts.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column("contact_type", sa.String(32), nullable=False),
            sa.Column("label", sa.String(100), nullable=True),
            sa.Column("contact_value", sa.String(320), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("visibility", sa.String(24), nullable=False, server_default="internal_only"),
            sa.Column("verification_status", sa.String(24), nullable=False, server_default="unverified"),
            sa.Column("lifecycle_status", sa.String(24), nullable=False, server_default="active"),
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
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("profile_id", "entry_key", "version", name="uq_personnel_contact_version"),
            sa.CheckConstraint("version > 0", name="ck_personnel_contact_version_positive"),
            sa.CheckConstraint(
                "contact_type IN ('corporate_email','alternative_email','business_phone','mobile_phone')",
                name="ck_personnel_contact_type",
            ),
            sa.CheckConstraint(
                "visibility IN ('internal_only','cv_eligible','share_eligible')",
                name="ck_personnel_contact_visibility",
            ),
            sa.CheckConstraint(
                "verification_status IN ('unverified','verified','rejected')",
                name="ck_personnel_contact_verification",
            ),
            sa.CheckConstraint(
                "lifecycle_status IN ('active','archived')",
                name="ck_personnel_contact_lifecycle",
            ),
        )
        for index_name, columns in (
            ("ix_personnel_contact_profile", ["profile_id"]),
            ("ix_personnel_contact_company", ["company_id"]),
            ("ix_personnel_contact_entry_key", ["entry_key"]),
            ("ix_personnel_contact_created_at", ["created_at"]),
        ):
            op.create_index(index_name, "personnel_profile_contacts", columns)

    if not inspector.has_table("personnel_profile_competencies"):
        op.create_table(
            "personnel_profile_competencies",
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
            sa.Column("entry_key", sa.String(36), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column(
                "supersedes_id",
                sa.Integer(),
                sa.ForeignKey("personnel_profile_competencies.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column("category", sa.String(40), nullable=False),
            sa.Column("name", sa.String(220), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("certificate_number", sa.String(120), nullable=True),
            sa.Column("issuing_organization", sa.String(220), nullable=True),
            sa.Column("description", sa.String(2000), nullable=True),
            sa.Column("verification_status", sa.String(24), nullable=False, server_default="unverified"),
            sa.Column("lifecycle_status", sa.String(24), nullable=False, server_default="active"),
            sa.Column("change_reason", sa.String(500), nullable=True),
            sa.Column(
                "created_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "approved_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("profile_id", "entry_key", "version", name="uq_personnel_competency_version"),
            sa.CheckConstraint("version > 0", name="ck_personnel_competency_version_positive"),
            sa.CheckConstraint(
                "category IN ('professional_duty','certificate_based','technical_specialization','training_authority','other')",
                name="ck_personnel_competency_category",
            ),
            sa.CheckConstraint(
                "verification_status IN ('unverified','verified','rejected')",
                name="ck_personnel_competency_verification",
            ),
            sa.CheckConstraint(
                "lifecycle_status IN ('active','archived')",
                name="ck_personnel_competency_lifecycle",
            ),
        )
        for index_name, columns in (
            ("ix_personnel_competency_profile", ["profile_id"]),
            ("ix_personnel_competency_company", ["company_id"]),
            ("ix_personnel_competency_entry_key", ["entry_key"]),
            ("ix_personnel_competency_category", ["category"]),
            ("ix_personnel_competency_created_at", ["created_at"]),
        ):
            op.create_index(index_name, "personnel_profile_competencies", columns)

    if not inspector.has_table("personnel_profile_experiences"):
        op.create_table(
            "personnel_profile_experiences",
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
            sa.Column("entry_key", sa.String(36), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column(
                "supersedes_id",
                sa.Integer(),
                sa.ForeignKey("personnel_profile_experiences.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column("organization_name", sa.String(220), nullable=False),
            sa.Column("position", sa.String(180), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("employment_type", sa.String(80), nullable=True),
            sa.Column("sector", sa.String(160), nullable=True),
            sa.Column("nace_activity", sa.String(300), nullable=True),
            sa.Column("project_name", sa.String(220), nullable=True),
            sa.Column("professional_summary", sa.String(2000), nullable=True),
            sa.Column("responsibilities", sa.Text(), nullable=True),
            sa.Column("visibility", sa.String(24), nullable=False, server_default="internal_only"),
            sa.Column("lifecycle_status", sa.String(24), nullable=False, server_default="active"),
            sa.Column("change_reason", sa.String(500), nullable=True),
            sa.Column(
                "created_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "approved_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("profile_id", "entry_key", "version", name="uq_personnel_experience_version"),
            sa.CheckConstraint("version > 0", name="ck_personnel_experience_version_positive"),
            sa.CheckConstraint(
                "visibility IN ('internal_only','cv_eligible')",
                name="ck_personnel_experience_visibility",
            ),
            sa.CheckConstraint(
                "lifecycle_status IN ('active','archived')",
                name="ck_personnel_experience_lifecycle",
            ),
        )
        for index_name, columns in (
            ("ix_personnel_experience_profile", ["profile_id"]),
            ("ix_personnel_experience_company", ["company_id"]),
            ("ix_personnel_experience_entry_key", ["entry_key"]),
            ("ix_personnel_experience_created_at", ["created_at"]),
        ):
            op.create_index(index_name, "personnel_profile_experiences", columns)

    for table, policy in (
        ("personnel_profiles", "personnel_profiles_company_scope"),
        ("personnel_profile_contacts", "personnel_profile_contacts_company_scope"),
        ("personnel_profile_competencies", "personnel_profile_competencies_company_scope"),
        ("personnel_profile_experiences", "personnel_profile_experiences_company_scope"),
    ):
        _enable_company_rls(table, policy)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = (
        ("personnel_profile_experiences", "personnel_profile_experiences_company_scope"),
        ("personnel_profile_competencies", "personnel_profile_competencies_company_scope"),
        ("personnel_profile_contacts", "personnel_profile_contacts_company_scope"),
        ("personnel_profiles", "personnel_profiles_company_scope"),
    )
    for table, policy in tables:
        if not inspector.has_table(table):
            continue
        if bind.dialect.name == "postgresql":
            op.execute(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"')
        op.drop_table(table)
