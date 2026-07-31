"""RLS expand: notifications (nullable company_id + user_id) (P1-03).

Revision ID: 0053
Revises: 0052

Policy:
- unset user / bypass: geç
- kendi user_id satırları
- company_id ∈ allowed_company_ids
- rls_admin: company_id NULL OSGB yayınları + rebuild insert

UI/flag değişmez.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = sa.inspect(bind)
    if not insp.has_table("notifications"):
        return

    op.execute(sa.text("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE notifications FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            DO $policy$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = current_schema()
                  AND tablename = 'notifications'
                  AND policyname = 'notifications_user_or_company_scope'
              ) THEN
                CREATE POLICY notifications_user_or_company_scope ON notifications
                  FOR ALL
                  USING (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                    OR (
                      notifications.user_id IS NOT NULL
                      AND notifications.user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
                    )
                    OR (
                      notifications.company_id IS NOT NULL
                      AND COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                      AND notifications.company_id = ANY (
                        string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                      )
                    )
                    OR (
                      COALESCE(current_setting('app.rls_admin', true), '') = '1'
                      AND notifications.company_id IS NULL
                    )
                  )
                  WITH CHECK (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                    OR COALESCE(current_setting('app.rls_admin', true), '') = '1'
                    OR (
                      notifications.user_id IS NOT NULL
                      AND notifications.user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
                    )
                    OR (
                      notifications.company_id IS NOT NULL
                      AND COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                      AND notifications.company_id = ANY (
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
    if not insp.has_table("notifications"):
        return
    op.execute(sa.text("DROP POLICY IF EXISTS notifications_user_or_company_scope ON notifications"))
    op.execute(sa.text("ALTER TABLE notifications NO FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE notifications DISABLE ROW LEVEL SECURITY"))
