"""Add per-workplace specialist/physician visit QR policy."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0119_company_visit_qr_policy"
down_revision: Union[str, None] = "0118_employee_exit_date"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "companies" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("companies")}
    if "visit_qr_enabled" in columns:
        return
    op.add_column(
        "companies",
        sa.Column("visit_qr_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    # Existing rows are enabled; future values are supplied by the ORM model.
    op.alter_column("companies", "visit_qr_enabled", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "companies" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("companies")}
    if "visit_qr_enabled" in columns:
        op.drop_column("companies", "visit_qr_enabled")
