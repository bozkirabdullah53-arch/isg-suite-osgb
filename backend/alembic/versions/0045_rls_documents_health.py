"""RLS expand: document_records + health_records (P1-03).

Revision ID: 0045
Revises: 0044

Policy: app.current_user_id boş → migrasyon/job geçişi;
rls_bypass=1 → global admin;
aksi halde company_id ∈ app.allowed_company_ids (CSV).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "document_records",
    "health_records",
)


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
                  USING (
                    {scope}
                  )
                  WITH CHECK (
                    {scope}
                  );
              END IF;
            END
            $policy$;
            """
        )
    )


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = sa.inspect(bind)
    for table in _TABLES:
        if insp.has_table(table):
            _enable_company_rls(table, f"{table}_company_scope")


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = sa.inspect(bind)
    for table in _TABLES:
        if not insp.has_table(table):
            continue
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_company_scope ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
