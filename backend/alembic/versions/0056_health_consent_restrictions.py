"""Health informed consent + restrictions + Pro exam types (additive).

Revision ID: 0056
Revises: 0055
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("health_records"):
        return
    cols = {c["name"] for c in insp.get_columns("health_records")}
    if "informed_consent" not in cols:
        op.add_column(
            "health_records",
            sa.Column("informed_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "informed_consent_at" not in cols:
        op.add_column("health_records", sa.Column("informed_consent_at", sa.DateTime(), nullable=True))
    if "restrictions" not in cols:
        op.add_column("health_records", sa.Column("restrictions", sa.Text(), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("health_records"):
        return
    cols = {c["name"] for c in insp.get_columns("health_records")}
    if "restrictions" in cols:
        op.drop_column("health_records", "restrictions")
    if "informed_consent_at" in cols:
        op.drop_column("health_records", "informed_consent_at")
    if "informed_consent" in cols:
        op.drop_column("health_records", "informed_consent")
