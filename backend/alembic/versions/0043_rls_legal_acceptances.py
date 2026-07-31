"""RLS pilot on legal_acceptances (P1-03).
Revision ID: 0043
Revises: 0042

Policy: app.current_user_id boşsa (migrasyon/job) geç; doluysa yalnız kendi satırları.
FORCE: tablo sahibi de RLS'e tabi (Render app rolü genelde owner).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = sa.inspect(bind)
    if not insp.has_table("legal_acceptances"):
        return

    op.execute(sa.text("ALTER TABLE legal_acceptances ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE legal_acceptances FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            DO $policy$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = current_schema()
                  AND tablename = 'legal_acceptances'
                  AND policyname = 'legal_acceptances_own_or_unset'
              ) THEN
                CREATE POLICY legal_acceptances_own_or_unset ON legal_acceptances
                  FOR ALL
                  USING (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
                  )
                  WITH CHECK (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
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
    if not insp.has_table("legal_acceptances"):
        return
    op.execute(sa.text("DROP POLICY IF EXISTS legal_acceptances_own_or_unset ON legal_acceptances"))
    op.execute(sa.text("ALTER TABLE legal_acceptances NO FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE legal_acceptances DISABLE ROW LEVEL SECURITY"))
