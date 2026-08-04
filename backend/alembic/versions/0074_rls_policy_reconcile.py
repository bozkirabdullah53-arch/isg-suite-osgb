"""PostgreSQL tenant RLS policy drift reconciliation.

Revision ID: 0074_rls_policy_reconcile
Revises: 0073_erecete_core

Production already carries these 33 policies while a database stamped at the
same Alembic head may not. This migration idempotently reconciles the approved
policy set without touching application data.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0074_rls_policy_reconcile"
down_revision = "0073_erecete_core"
branch_labels = None
depends_on = None


DIRECT_COMPANY_POLICIES: dict[str, str] = {
    "annual_plan_evaluation_items": "annual_plan_evaluation_items_company_scope",
    "annual_plan_evaluations": "annual_plan_evaluations_company_scope",
    "annual_plan_items": "annual_plan_items_company_scope",
    "annual_plan_unplanned_activities": "annual_plan_unplanned_activities_company_scope",
    "branches": "branches_company_scope",
    "chemical_products": "chemical_products_company_scope",
    "company_subscriptions": "company_subscriptions_company_scope",
    "document_records": "document_records_company_scope",
    "drill_records": "drill_records_company_scope",
    "e_sign_artifacts": "e_sign_artifacts_company_isolation",
    "e_sign_requests": "e_sign_requests_company_isolation",
    "e_signature_audit_events": "e_signature_audit_events_company_isolation",
    "e_signature_requests": "e_signature_requests_company_isolation",
    "emergency_plan_floors": "rls_emergency_plan_floors_company",
    "emergency_team_assignments": "emergency_team_assignments_company_scope",
    "emergency_teams": "emergency_teams_company_scope",
    "employees": "employees_company_scope",
    "health_records": "health_records_company_scope",
    "incident_events": "incident_events_company_scope",
    "isg_records": "isg_records_company_scope",
    "ppe_assignments": "ppe_assignments_company_scope",
    "risk_assessments": "risk_assessments_company_scope",
    "service_contracts": "service_contracts_company_scope",
    "service_visits": "service_visits_company_scope",
    "site_qr_sessions": "site_qr_sessions_company_scope",
    "training_sessions": "training_sessions_company_scope",
    "workplace_assignments": "workplace_assignments_company_scope",
    "workplace_departments": "workplace_departments_company_scope",
}

SPECIAL_POLICY_TABLES = {
    "companies",
    "legal_acceptances",
    "notifications",
    "organization_memberships",
    "workplace_memberships",
}

_UNSET = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
_BYPASS = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
_ADMIN = "COALESCE(current_setting('app.rls_admin', true), '') = '1'"
_CURRENT_USER = "NULLIF(current_setting('app.current_user_id', true), '')::integer"
_ALLOWED_IDS = (
    "string_to_array("
    "COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), "
    "','"
    ")::integer[]"
)
_COMPANY_SCOPE = f"({_UNSET}) OR ({_BYPASS}) OR (company_id = ANY ({_ALLOWED_IDS}))"
_COMPANY_ID_SCOPE = f"({_UNSET}) OR ({_BYPASS}) OR (id = ANY ({_ALLOWED_IDS}))"


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _drop_all_policies(table_name: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT p.polname
            FROM pg_policy p
            JOIN pg_class c ON c.oid = p.polrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = :table_name
            """
        ),
        {"table_name": table_name},
    ).scalars().all()
    for policy_name in rows:
        op.execute(
            f"DROP POLICY IF EXISTS {_quote(str(policy_name))} "
            f"ON {_quote(table_name)}"
        )


def _reconcile_policy(
    table_name: str,
    policy_name: str,
    using_expression: str,
    check_expression: str | None = None,
) -> None:
    if not _table_exists(table_name):
        return
    _drop_all_policies(table_name)
    op.execute(f"ALTER TABLE {_quote(table_name)} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_quote(table_name)} FORCE ROW LEVEL SECURITY")
    check = check_expression or using_expression
    op.execute(
        f"CREATE POLICY {_quote(policy_name)} ON {_quote(table_name)} "
        f"FOR ALL USING ({using_expression}) WITH CHECK ({check})"
    )


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return

    for table_name, policy_name in DIRECT_COMPANY_POLICIES.items():
        _reconcile_policy(table_name, policy_name, _COMPANY_SCOPE)

    _reconcile_policy(
        "companies",
        "companies_allowed_scope",
        _COMPANY_ID_SCOPE,
        f"({_COMPANY_ID_SCOPE}) OR ({_ADMIN})",
    )
    _reconcile_policy(
        "legal_acceptances",
        "legal_acceptances_own_or_unset",
        f"({_UNSET}) OR (user_id = {_CURRENT_USER})",
    )
    _reconcile_policy(
        "organization_memberships",
        "organization_memberships_own_or_unset",
        f"({_UNSET}) OR (user_id = {_CURRENT_USER}) OR ({_ADMIN})",
    )
    _reconcile_policy(
        "workplace_memberships",
        "workplace_memberships_own_or_unset",
        f"({_UNSET}) OR (user_id = {_CURRENT_USER}) OR ({_ADMIN})",
    )

    notifications_using = (
        f"({_UNSET}) OR ({_BYPASS}) "
        f"OR ((user_id IS NOT NULL) AND (user_id = {_CURRENT_USER})) "
        f"OR ((company_id IS NOT NULL) AND (company_id = ANY ({_ALLOWED_IDS}))) "
        f"OR (({_ADMIN}) AND (company_id IS NULL))"
    )
    notifications_check = (
        f"({_UNSET}) OR ({_BYPASS}) OR ({_ADMIN}) "
        f"OR ((user_id IS NOT NULL) AND (user_id = {_CURRENT_USER})) "
        f"OR ((company_id IS NOT NULL) AND (company_id = ANY ({_ALLOWED_IDS})))"
    )
    _reconcile_policy(
        "notifications",
        "notifications_user_or_company_scope",
        notifications_using,
        notifications_check,
    )


def downgrade():
    # Security reconciliation is intentionally non-destructive on downgrade.
    # Removing policies could expose cross-tenant data on databases that already
    # had the approved policy set before this revision was applied.
    pass
