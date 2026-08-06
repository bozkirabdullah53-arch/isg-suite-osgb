"""Scope professional digital cards to their OSGB, never a service workplace.

Revision ID: 0083_personnel_profile_osgb_scope
Revises: 0082_personnel_profile_documents
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0083_personnel_profile_osgb_scope"
down_revision: Union[str, None] = "0082_personnel_profile_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROFILE_CHILDREN = (
    "personnel_profile_contacts",
    "personnel_profile_competencies",
    "personnel_profile_experiences",
    "personnel_profile_documents",
)


def _drop_policy(table: str, policy: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"')


def _install_profile_policy() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    unset = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
    bypass = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
    allowed = (
        "string_to_array(COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), ',')::integer[]"
    )
    current_osgb = "NULLIF(current_setting('app.current_osgb_id', true), '')::integer"
    scope = (
        f"({unset}) OR ({bypass}) OR "
        f"(company_id IS NOT NULL AND company_id = ANY ({allowed})) OR "
        f"(subject_type = 'professional' AND company_id IS NULL AND osgb_id = {current_osgb})"
    )
    op.execute('ALTER TABLE "personnel_profiles" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "personnel_profiles" FORCE ROW LEVEL SECURITY')
    _drop_policy("personnel_profiles", "personnel_profiles_company_scope")
    op.execute(
        'CREATE POLICY "personnel_profiles_tenant_scope" ON "personnel_profiles" '
        f"FOR ALL USING ({scope}) WITH CHECK ({scope})"
    )


def _install_child_policy(table: str, old_policy: str, new_policy: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    unset = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
    bypass = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
    allowed = (
        "string_to_array(COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), ',')::integer[]"
    )
    current_osgb = "NULLIF(current_setting('app.current_osgb_id', true), '')::integer"
    scope = (
        f"({unset}) OR ({bypass}) OR "
        f"(company_id IS NOT NULL AND company_id = ANY ({allowed})) OR EXISTS ("
        f"SELECT 1 FROM personnel_profiles p WHERE p.id = {table}.profile_id "
        f"AND p.subject_type = 'professional' AND p.company_id IS NULL "
        f"AND p.osgb_id = {current_osgb})"
    )
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    _drop_policy(table, old_policy)
    op.execute(
        f'CREATE POLICY "{new_policy}" ON "{table}" '
        f"FOR ALL USING ({scope}) WITH CHECK ({scope})"
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("personnel_profiles"):
        return

    columns = {column["name"] for column in inspector.get_columns("personnel_profiles")}
    if "legacy_company_id" not in columns:
        op.add_column("personnel_profiles", sa.Column("legacy_company_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_personnel_profiles_legacy_company",
            "personnel_profiles",
            "companies",
            ["legacy_company_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    # Preserve the former workplace link only for reversible historical reference.
    op.execute(
        "UPDATE personnel_profiles SET legacy_company_id = company_id "
        "WHERE subject_type = 'professional' AND legacy_company_id IS NULL"
    )

    # Child rows inherit OSGB scope through their parent profile.
    for table in _PROFILE_CHILDREN:
        if inspector.has_table(table):
            op.execute(
                f"UPDATE {table} c SET company_id = NULL "
                "FROM personnel_profiles p "
                f"WHERE c.profile_id = p.id AND p.subject_type = 'professional'"
            ) if bind.dialect.name == "postgresql" else None

    with op.batch_alter_table("personnel_profiles") as batch:
        batch.drop_constraint("uq_personnel_profile_company_professional", type_="unique")
        batch.drop_constraint("ck_personnel_profile_exact_subject", type_="check")
        batch.alter_column("company_id", existing_type=sa.Integer(), nullable=True)
        batch.create_unique_constraint(
            "uq_personnel_profile_osgb_professional", ["osgb_id", "professional_id"]
        )
        batch.create_check_constraint(
            "ck_personnel_profile_exact_subject",
            "(subject_type = 'employee' AND company_id IS NOT NULL AND employee_id IS NOT NULL AND professional_id IS NULL) "
            "OR (subject_type = 'professional' AND company_id IS NULL AND professional_id IS NOT NULL AND employee_id IS NULL)",
        )

    op.execute(
        "UPDATE personnel_profiles SET company_id = NULL "
        "WHERE subject_type = 'professional'"
    )

    for table in _PROFILE_CHILDREN:
        if not inspector.has_table(table):
            continue
        if bind.dialect.name != "postgresql":
            op.execute(
                f"UPDATE {table} SET company_id = NULL WHERE profile_id IN "
                "(SELECT id FROM personnel_profiles WHERE subject_type = 'professional')"
            )
        with op.batch_alter_table(table) as batch:
            batch.alter_column("company_id", existing_type=sa.Integer(), nullable=True)

    _install_profile_policy()
    child_policies = (
        ("personnel_profile_contacts", "personnel_profile_contacts_company_scope", "personnel_profile_contacts_tenant_scope"),
        ("personnel_profile_competencies", "personnel_profile_competencies_company_scope", "personnel_profile_competencies_tenant_scope"),
        ("personnel_profile_experiences", "personnel_profile_experiences_company_scope", "personnel_profile_experiences_tenant_scope"),
        ("personnel_profile_documents", "personnel_profile_documents_company_scope", "personnel_profile_documents_tenant_scope"),
    )
    for table, old_policy, new_policy in child_policies:
        if inspector.has_table(table):
            _install_child_policy(table, old_policy, new_policy)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("personnel_profiles"):
        return

    missing_legacy = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM personnel_profiles "
            "WHERE subject_type = 'professional' AND legacy_company_id IS NULL"
        )
    ).scalar_one()
    if int(missing_legacy or 0) > 0:
        raise RuntimeError(
            "OSGB-scoped professional profiles without a historical company cannot be downgraded safely. "
            "Use feature force-off and a forward migration instead."
        )

    op.execute(
        "UPDATE personnel_profiles SET company_id = legacy_company_id "
        "WHERE subject_type = 'professional'"
    )
    for table in _PROFILE_CHILDREN:
        if not inspector.has_table(table):
            continue
        if bind.dialect.name == "postgresql":
            op.execute(
                f"UPDATE {table} c SET company_id = p.company_id "
                "FROM personnel_profiles p WHERE c.profile_id = p.id AND c.company_id IS NULL"
            )
        else:
            op.execute(
                f"UPDATE {table} SET company_id = (SELECT p.company_id FROM personnel_profiles p "
                f"WHERE p.id = {table}.profile_id) WHERE company_id IS NULL"
            )
        with op.batch_alter_table(table) as batch:
            batch.alter_column("company_id", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("personnel_profiles") as batch:
        batch.drop_constraint("uq_personnel_profile_osgb_professional", type_="unique")
        batch.drop_constraint("ck_personnel_profile_exact_subject", type_="check")
        batch.alter_column("company_id", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint(
            "uq_personnel_profile_company_professional", ["company_id", "professional_id"]
        )
        batch.create_check_constraint(
            "ck_personnel_profile_exact_subject",
            "(subject_type = 'employee' AND employee_id IS NOT NULL AND professional_id IS NULL) "
            "OR (subject_type = 'professional' AND professional_id IS NOT NULL AND employee_id IS NULL)",
        )
        batch.drop_constraint("fk_personnel_profiles_legacy_company", type_="foreignkey")
        batch.drop_column("legacy_company_id")

    if bind.dialect.name == "postgresql":
        _drop_policy("personnel_profiles", "personnel_profiles_tenant_scope")
        for table, _, new_policy in (
            ("personnel_profile_contacts", "", "personnel_profile_contacts_tenant_scope"),
            ("personnel_profile_competencies", "", "personnel_profile_competencies_tenant_scope"),
            ("personnel_profile_experiences", "", "personnel_profile_experiences_tenant_scope"),
            ("personnel_profile_documents", "", "personnel_profile_documents_tenant_scope"),
        ):
            if inspector.has_table(table):
                _drop_policy(table, new_policy)
