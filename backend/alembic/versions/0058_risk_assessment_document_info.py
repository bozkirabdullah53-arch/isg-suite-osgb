"""Risk assessment document date + team fields on companies (additive).

Revision ID: 0058
Revises: 0057
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    if "risk_assessment_date" not in cols:
        op.add_column("companies", sa.Column("risk_assessment_date", sa.Date(), nullable=True))
    if "risk_team_employee_rep" not in cols:
        op.add_column("companies", sa.Column("risk_team_employee_rep", sa.String(length=160), nullable=True))
    if "risk_team_support_staff" not in cols:
        op.add_column("companies", sa.Column("risk_team_support_staff", sa.String(length=160), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    if "risk_team_support_staff" in cols:
        op.drop_column("companies", "risk_team_support_staff")
    if "risk_team_employee_rep" in cols:
        op.drop_column("companies", "risk_team_employee_rep")
    if "risk_assessment_date" in cols:
        op.drop_column("companies", "risk_assessment_date")
