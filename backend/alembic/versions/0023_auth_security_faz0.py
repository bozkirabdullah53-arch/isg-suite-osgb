"""Auth hardening, password reset, MFA columns.
Revision ID: 0023
Revises: 0022
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("users"):
        cols = {c["name"] for c in insp.get_columns("users")}
        with op.batch_alter_table("users") as batch:
            if "failed_login_count" not in cols:
                batch.add_column(sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False))
            if "locked_until" not in cols:
                batch.add_column(sa.Column("locked_until", sa.DateTime(), nullable=True))
            if "mfa_enabled" not in cols:
                batch.add_column(sa.Column("mfa_enabled", sa.Boolean(), server_default="0", nullable=False))
            if "mfa_secret_encrypted" not in cols:
                batch.add_column(sa.Column("mfa_secret_encrypted", sa.String(500), nullable=True))
            if "mfa_recovery_hashes" not in cols:
                batch.add_column(sa.Column("mfa_recovery_hashes", sa.Text(), nullable=True))

    if not insp.has_table("password_reset_tokens"):
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(128), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
        op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)
        op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("password_reset_tokens"):
        op.drop_table("password_reset_tokens")
    if insp.has_table("users"):
        cols = {c["name"] for c in insp.get_columns("users")}
        with op.batch_alter_table("users") as batch:
            for name in (
                "mfa_recovery_hashes",
                "mfa_secret_encrypted",
                "mfa_enabled",
                "locked_until",
                "failed_login_count",
            ):
                if name in cols:
                    batch.drop_column(name)
