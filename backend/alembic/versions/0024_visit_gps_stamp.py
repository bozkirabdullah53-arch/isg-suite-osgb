"""GPS stamp columns on service_visits (Faz 2 saha).
Revision ID: 0024
Revises: 0023
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("service_visits"):
        return
    cols = {c["name"] for c in insp.get_columns("service_visits")}
    with op.batch_alter_table("service_visits") as batch:
        if "gps_lat" not in cols:
            batch.add_column(sa.Column("gps_lat", sa.Float(), nullable=True))
        if "gps_lng" not in cols:
            batch.add_column(sa.Column("gps_lng", sa.Float(), nullable=True))
        if "gps_accuracy_m" not in cols:
            batch.add_column(sa.Column("gps_accuracy_m", sa.Float(), nullable=True))
        if "gps_captured_at" not in cols:
            batch.add_column(sa.Column("gps_captured_at", sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("service_visits"):
        return
    cols = {c["name"] for c in insp.get_columns("service_visits")}
    with op.batch_alter_table("service_visits") as batch:
        for name in ("gps_captured_at", "gps_accuracy_m", "gps_lng", "gps_lat"):
            if name in cols:
                batch.drop_column(name)
