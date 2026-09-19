"""Add employment exit date to employee records."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0118_employee_exit_date"
down_revision: Union[str, None] = "0117_remote_workplace_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "employees" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("employees")}
    if "exit_date" not in columns:
        op.add_column("employees", sa.Column("exit_date", sa.Date(), nullable=True))
        op.create_index("ix_employees_exit_date", "employees", ["exit_date"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "employees" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("employees")}
    if "exit_date" in columns:
        indexes = {index["name"] for index in inspector.get_indexes("employees")}
        if "ix_employees_exit_date" in indexes:
            op.drop_index("ix_employees_exit_date", table_name="employees")
        op.drop_column("employees", "exit_date")
