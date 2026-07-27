"""User e-signature profile (visual stamp + bridge meta).

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
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "e_signature_file_name" not in cols:
        op.add_column("users", sa.Column("e_signature_file_name", sa.String(255), nullable=True))
    if "e_signature_storage_path" not in cols:
        op.add_column("users", sa.Column("e_signature_storage_path", sa.String(500), nullable=True))
    if "e_signature_uploaded_at" not in cols:
        op.add_column("users", sa.Column("e_signature_uploaded_at", sa.DateTime(), nullable=True))
    if "e_signature_title" not in cols:
        op.add_column("users", sa.Column("e_signature_title", sa.String(120), nullable=True))
    if "e_signature_bridge_status" not in cols:
        op.add_column(
            "users",
            sa.Column("e_signature_bridge_status", sa.String(40), nullable=True),
        )
    if "e_signature_bridge_checked_at" not in cols:
        op.add_column("users", sa.Column("e_signature_bridge_checked_at", sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    for col in (
        "e_signature_bridge_checked_at",
        "e_signature_bridge_status",
        "e_signature_title",
        "e_signature_uploaded_at",
        "e_signature_storage_path",
        "e_signature_file_name",
    ):
        if col in cols:
            op.drop_column("users", col)
