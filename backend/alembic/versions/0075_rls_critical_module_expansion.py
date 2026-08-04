"""Expand tenant RLS to critical modules added after the original policy set.

Revision ID: 0075_rls_critical_expand
Revises: 0074_rls_policy_reconcile

This revision protects ten non-null company-scoped tables and the e-prescription
child hierarchy. It does not modify application data.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0075_rls_critical_expand"
down_revision = "0074_rls_policy_reconcile"
branch_labels = None
depends_on = None


DIRECT_COMPANY_POLICIES: dict[str, str] = {
    "document_approvals": "document_approvals_company_scope",
    "emergency_plans": "emergency_plans_company_scope",
    "eyas_events": "eyas_events_company_scope",
    "eyas_steps": "eyas_steps_company_scope",
    "eyas_workflows": "eyas_workflows_company_scope",
    "ohs_committee_meetings": "ohs_committee_meetings_company_scope",
    "ohs_committee_members": "ohs_committee_members_company_scope",
    "periodic_controls": "periodic_controls_company_scope",
    "prescriptions": "prescriptions_company_scope",
    "workplace_measurements": "workplace_measurements_company_scope",
}

_UNSET = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
_BYPASS = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
_ADMIN = "COALESCE(current_setting('app.rls_admin', true), '') = '1'"
_ALLOWED_IDS = (
    "string_to_array("
    "COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), "
    "','"
    ")::integer[]"
)
_COMPANY_SCOPE = f"({_UNSET}) OR ({_BYPASS}) OR (company_id = ANY ({_ALLOWED_IDS}))"


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


def _prescription_scope(prescription_reference: str) -> str:
    return (
        f"({_UNSET}) OR ({_BYPASS}) OR EXISTS ("
        "SELECT 1 FROM prescriptions p "
        f"WHERE p.id = {prescription_reference} "
        f"AND p.company_id = ANY ({_ALLOWED_IDS})"
        ")"
    )


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return

    for table_name, policy_name in DIRECT_COMPANY_POLICIES.items():
        _reconcile_policy(table_name, policy_name, _COMPANY_SCOPE)

    _reconcile_policy(
        "prescription_items",
        "prescription_items_company_scope",
        _prescription_scope("prescription_items.prescription_id"),
    )
    _reconcile_policy(
        "prescription_submissions",
        "prescription_submissions_company_scope",
        _prescription_scope("prescription_submissions.prescription_id"),
    )

    attempts_scope = (
        f"({_UNSET}) OR ({_BYPASS}) OR EXISTS ("
        "SELECT 1 "
        "FROM prescription_submissions s "
        "JOIN prescriptions p ON p.id = s.prescription_id "
        "WHERE s.id = prescription_submission_attempts.submission_id "
        f"AND p.company_id = ANY ({_ALLOWED_IDS})"
        ")"
    )
    _reconcile_policy(
        "prescription_submission_attempts",
        "prescription_submission_attempts_company_scope",
        attempts_scope,
    )

    medula_scope = (
        f"({_UNSET}) OR ({_BYPASS}) "
        "OR ((medula_error_logs.prescription_id IS NOT NULL) AND EXISTS ("
        "SELECT 1 FROM prescriptions p "
        "WHERE p.id = medula_error_logs.prescription_id "
        f"AND p.company_id = ANY ({_ALLOWED_IDS})"
        ")) "
        "OR ((medula_error_logs.submission_id IS NOT NULL) AND EXISTS ("
        "SELECT 1 FROM prescription_submissions s "
        "JOIN prescriptions p ON p.id = s.prescription_id "
        "WHERE s.id = medula_error_logs.submission_id "
        f"AND p.company_id = ANY ({_ALLOWED_IDS})"
        ")) "
        "OR ((medula_error_logs.prescription_id IS NULL) "
        "AND (medula_error_logs.submission_id IS NULL) "
        f"AND ({_ADMIN}))"
    )
    _reconcile_policy(
        "medula_error_logs",
        "medula_error_logs_company_scope",
        medula_scope,
    )


def downgrade():
    # Do not remove tenant security on downgrade. Apply a forward migration for
    # any policy correction instead of reopening protected tables.
    pass
