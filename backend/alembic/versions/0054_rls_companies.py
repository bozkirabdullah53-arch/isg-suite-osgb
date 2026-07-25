"""RLS expand: companies (id ∈ allowed) (P1-03).

Revision ID: 0054
Revises: 0053

SELECT: allowed_company_ids veya bypass.
INSERT/UPDATE: rls_admin (OSGB/global) veya id∈allowed.
UI/flag değişmez.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0054"
down_revision: Union[str, None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return

    op.execute(sa.text("ALTER TABLE companies ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE companies FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            DO $policy$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = current_schema()
                  AND tablename = 'companies'
                  AND policyname = 'companies_allowed_scope'
              ) THEN
                CREATE POLICY companies_allowed_scope ON companies
                  FOR ALL
                  USING (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                    OR (
                      COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                      AND companies.id = ANY (
                        string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                      )
                    )
                  )
                  WITH CHECK (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                    OR COALESCE(current_setting('app.rls_admin', true), '') = '1'
                    OR (
                      COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                      AND companies.id = ANY (
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


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    op.execute(sa.text("DROP POLICY IF EXISTS companies_allowed_scope ON companies"))
    op.execute(sa.text("ALTER TABLE companies NO FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE companies DISABLE ROW LEVEL SECURITY"))
