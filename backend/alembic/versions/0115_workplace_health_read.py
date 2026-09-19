"""Allow scoped workplace medical SELECTs without clinical write privileges."""
from alembic import op
import sqlalchemy as sa

revision = "0115_workplace_health_read"
down_revision = "0114_email_inbox_attachments"
branch_labels = None
depends_on = None

SCOPE = """
COALESCE(current_setting('app.health_workplace_read', true), '') = '1'
AND company_id = NULLIF(current_setting('app.current_company_id', true), '')::integer
AND company_id = ANY(string_to_array(
    COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), ','
)::integer[])
"""


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    # Existing clinical write policies and append-only triggers stay intact.
    for table in ("health_records", "health_access_logs"):
        op.execute(sa.text(f"CREATE POLICY {table}_workplace_read ON {table} FOR SELECT USING ({SCOPE})"))
    op.execute(sa.text(f"""CREATE POLICY health_access_logs_workplace_append
        ON health_access_logs FOR INSERT WITH CHECK (
            ({SCOPE}) AND actor_user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
        )"""))


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(sa.text("DROP POLICY IF EXISTS health_access_logs_workplace_append ON health_access_logs"))
    for table in ("health_records", "health_access_logs"):
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_workplace_read ON {table}"))
