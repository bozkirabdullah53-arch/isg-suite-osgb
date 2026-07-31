"""RLS expand: memberships (P1-03).
Revision ID: 0044
Revises: 0043
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "organization_memberships",
    "workplace_memberships",
)


def _enable_own_user_rls(table: str, policy: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
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
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
                    OR COALESCE(current_setting('app.rls_admin', true), '') = '1'
                  )
                  WITH CHECK (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
                    OR COALESCE(current_setting('app.rls_admin', true), '') = '1'
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
            _enable_own_user_rls(table, f"{table}_own_or_unset")


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = sa.inspect(bind)
    for table in _TABLES:
        if not insp.has_table(table):
            continue
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_own_or_unset ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
