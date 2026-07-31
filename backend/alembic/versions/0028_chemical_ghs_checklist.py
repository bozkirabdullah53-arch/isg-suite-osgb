"""GHS checklist column on chemical_products.
Revision ID: 0028
Revises: 0027
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("chemical_products"):
        return
    cols = {c["name"] for c in insp.get_columns("chemical_products")}
    if "ghs_checklist_json" not in cols:
        with op.batch_alter_table("chemical_products") as batch:
            batch.add_column(sa.Column("ghs_checklist_json", sa.String(500), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("chemical_products"):
        return
    cols = {c["name"] for c in insp.get_columns("chemical_products")}
    if "ghs_checklist_json" in cols:
        with op.batch_alter_table("chemical_products") as batch:
            batch.drop_column("ghs_checklist_json")
