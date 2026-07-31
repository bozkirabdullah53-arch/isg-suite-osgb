"""Revision ID: 0017
Revises: 0016
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("osgb_applications"):
        return

    cols = {c["name"] for c in insp.get_columns("osgb_applications")}

    with op.batch_alter_table("osgb_applications") as batch:
        if "contract_accepted" not in cols:
            batch.add_column(
                sa.Column(
                    "contract_accepted",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        if "personal_data_accepted" not in cols:
            batch.add_column(
                sa.Column(
                    "personal_data_accepted",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("osgb_applications"):
        return

    cols = {c["name"] for c in insp.get_columns("osgb_applications")}

    with op.batch_alter_table("osgb_applications") as batch:
        if "personal_data_accepted" in cols:
            batch.drop_column("personal_data_accepted")
        if "contract_accepted" in cols:
            batch.drop_column("contract_accepted")

