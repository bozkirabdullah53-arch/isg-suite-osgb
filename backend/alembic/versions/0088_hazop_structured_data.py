"""Add nullable structured HAZOP data to risk assessments.

Revision ID: 0088_hazop_structured_data
Revises: 0087_fine_kinney_method_fields
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0088_hazop_structured_data"
down_revision: Union[str, None] = "0087_fine_kinney_method_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _risk_table_exists() -> bool:
    return sa.inspect(op.get_bind()).has_table("risk_assessments")


def upgrade() -> None:
    if not _risk_table_exists():
        return
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("risk_assessments")}
    if "hazop_data_json" not in columns:
        op.add_column(
            "risk_assessments",
            sa.Column("hazop_data_json", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if not _risk_table_exists():
        return
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("risk_assessments")}
    if "hazop_data_json" in columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("risk_assessments", recreate="always") as batch:
                batch.drop_column("hazop_data_json")
        else:
            op.drop_column("risk_assessments", "hazop_data_json")
