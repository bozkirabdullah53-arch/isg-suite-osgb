"""Add a tenant-scoped responsible employee to risk assessments.

The column is nullable for backward compatibility with existing risk rows.
New assignments are validated by the risk API against the same company and
active employee scope before they are persisted.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0101_risk_responsible_employee"
down_revision: Union[str, None] = "0094_repair_catalog_sector2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "risk_assessments" not in tables or "employees" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("risk_assessments")}
    if "responsible_employee_id" not in columns:
        op.add_column(
            "risk_assessments",
            sa.Column(
                "responsible_employee_id",
                sa.Integer(),
                sa.ForeignKey("employees.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    indexes = {index.get("name") for index in sa.inspect(bind).get_indexes("risk_assessments")}
    if "ix_risk_assessments_responsible_employee_id" not in indexes:
        op.create_index(
            "ix_risk_assessments_responsible_employee_id",
            "risk_assessments",
            ["responsible_employee_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "risk_assessments" not in set(inspector.get_table_names()):
        return

    indexes = {index.get("name") for index in inspector.get_indexes("risk_assessments")}
    if "ix_risk_assessments_responsible_employee_id" in indexes:
        op.drop_index(
            "ix_risk_assessments_responsible_employee_id",
            table_name="risk_assessments",
        )

    columns = {column["name"] for column in sa.inspect(bind).get_columns("risk_assessments")}
    if "responsible_employee_id" in columns:
        with op.batch_alter_table("risk_assessments") as batch:
            batch.drop_column("responsible_employee_id")
