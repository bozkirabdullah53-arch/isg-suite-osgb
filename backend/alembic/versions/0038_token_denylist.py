"""JWT denylist + users.token_version.
Revision ID: 0038
Revises: 0037
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("users"):
        cols = {c["name"] for c in insp.get_columns("users")}
        if "token_version" not in cols:
            with op.batch_alter_table("users") as batch:
                batch.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))

    if not insp.has_table("token_denylist"):
        op.create_table(
            "token_denylist",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("jti", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_token_denylist_jti", "token_denylist", ["jti"], unique=True)
        op.create_index("ix_token_denylist_expires_at", "token_denylist", ["expires_at"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("token_denylist"):
        op.drop_index("ix_token_denylist_expires_at", table_name="token_denylist")
        op.drop_index("ix_token_denylist_jti", table_name="token_denylist")
        op.drop_table("token_denylist")
    if insp.has_table("users"):
        cols = {c["name"] for c in insp.get_columns("users")}
        if "token_version" in cols:
            with op.batch_alter_table("users") as batch:
                batch.drop_column("token_version")
