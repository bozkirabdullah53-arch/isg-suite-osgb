"""Repair: ensure risk document columns exist on companies.

Revision 0058 was first used by a reverted migration, so databases already
stamped "0058" skipped the risk document columns and every companies query
failed. This revision re-applies them idempotently.

Revision ID: 0059
Revises: 0058
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0059"
down_revision: Union[str, None] = "0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    ("risk_assessment_date", sa.Date()),
    ("risk_team_employee_rep", sa.String(length=160)),
    ("risk_team_support_staff", sa.String(length=160)),
)


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    for name, type_ in COLUMNS:
        if name not in cols:
            op.add_column("companies", sa.Column(name, type_, nullable=True))


def downgrade():
    # 0058 owns these columns; repair-only revision drops nothing.
    pass
