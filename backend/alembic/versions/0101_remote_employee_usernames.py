"""Add optional usernames for password-based employee logins.

Revision ID: 0101_remote_employee_usernames
Revises: 0100_employee_national_scope
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0101_remote_employee_usernames"
down_revision: Union[str, None] = "0100_employee_national_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _indexes(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {index["name"] for index in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("users"):
        return

    if "username" not in _columns("users"):
        op.add_column(
            "users",
            sa.Column("username", sa.String(length=160), nullable=True),
        )

    if "ix_users_username" not in _indexes("users"):
        op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("users"):
        return

    if "ix_users_username" in _indexes("users"):
        op.drop_index("ix_users_username", table_name="users")
    if "username" in _columns("users"):
        op.drop_column("users", "username")
