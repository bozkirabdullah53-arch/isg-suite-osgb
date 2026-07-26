"""ServiceVisit checked_in_at / checked_out_at (QR kiosk süre).

Revision ID: 0055
Revises: 0054
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: Union[str, None] = "0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("service_visits"):
        return
    cols = {c["name"] for c in insp.get_columns("service_visits")}
    if "checked_in_at" not in cols:
        op.add_column("service_visits", sa.Column("checked_in_at", sa.DateTime(), nullable=True))
        op.create_index("ix_service_visits_checked_in_at", "service_visits", ["checked_in_at"])
    if "checked_out_at" not in cols:
        op.add_column("service_visits", sa.Column("checked_out_at", sa.DateTime(), nullable=True))
        op.create_index("ix_service_visits_checked_out_at", "service_visits", ["checked_out_at"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("service_visits"):
        return
    cols = {c["name"] for c in insp.get_columns("service_visits")}
    if "checked_out_at" in cols:
        op.drop_index("ix_service_visits_checked_out_at", table_name="service_visits")
        op.drop_column("service_visits", "checked_out_at")
    if "checked_in_at" in cols:
        op.drop_index("ix_service_visits_checked_in_at", table_name="service_visits")
        op.drop_column("service_visits", "checked_in_at")
