"""Revision ID: 0021
Revises: 0020

annual_plan_items.status: Postgres native enum → VARCHAR.
Live DB enum labels (often PLANNED vs planned) caused InvalidTextRepresentation.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = sa.inspect(bind)
    if not insp.has_table("annual_plan_items"):
        return
    cols = {c["name"]: c for c in insp.get_columns("annual_plan_items")}
    col = cols.get("status")
    if not col:
        return
    # Already varchar / text — normalize values only
    typ = str(col.get("type") or "").lower()
    if "char" in typ or "text" in typ:
        op.execute(
            sa.text(
                """
                UPDATE annual_plan_items
                SET status = lower(status)
                WHERE status IS NOT NULL AND status <> lower(status)
                """
            )
        )
        return

    # Native enum → varchar with lowercase values
    op.execute(
        sa.text(
            """
            ALTER TABLE annual_plan_items
            ALTER COLUMN status TYPE VARCHAR(40)
            USING lower(status::text)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE annual_plan_items
            SET status = 'planned'
            WHERE status IS NULL OR status = ''
            """
        )
    )
    # Drop orphaned enum type if nothing else uses it (best-effort)
    try:
        op.execute(sa.text("DROP TYPE IF EXISTS annualplanstatus"))
    except Exception:
        pass


def downgrade():
    # Recreating native enum is lossy; leave as VARCHAR.
    pass
