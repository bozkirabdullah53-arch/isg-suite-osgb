"""Visit signature stamp columns.
Revision ID: 0026
Revises: 0025
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("service_visits"):
        return
    cols = {c["name"] for c in insp.get_columns("service_visits")}
    with op.batch_alter_table("service_visits") as batch:
        if "signature_file_name" not in cols:
            batch.add_column(sa.Column("signature_file_name", sa.String(255), nullable=True))
        if "signature_storage_path" not in cols:
            batch.add_column(sa.Column("signature_storage_path", sa.String(500), nullable=True))
        if "signature_captured_at" not in cols:
            batch.add_column(sa.Column("signature_captured_at", sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("service_visits"):
        return
    cols = {c["name"] for c in insp.get_columns("service_visits")}
    with op.batch_alter_table("service_visits") as batch:
        for name in ("signature_captured_at", "signature_storage_path", "signature_file_name"):
            if name in cols:
                batch.drop_column(name)
