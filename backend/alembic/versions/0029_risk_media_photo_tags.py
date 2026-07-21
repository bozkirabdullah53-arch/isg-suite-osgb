"""Risk media photo tags column.
Revision ID: 0029
Revises: 0028
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("risk_media"):
        return
    cols = {c["name"] for c in insp.get_columns("risk_media")}
    if "tags_json" not in cols:
        with op.batch_alter_table("risk_media") as batch:
            batch.add_column(sa.Column("tags_json", sa.String(500), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("risk_media"):
        return
    cols = {c["name"] for c in insp.get_columns("risk_media")}
    if "tags_json" in cols:
        with op.batch_alter_table("risk_media") as batch:
            batch.drop_column("tags_json")
