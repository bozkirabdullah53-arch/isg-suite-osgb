"""Additive source metadata for imported 5x5 risk workbooks.

Only nullable columns are added. Existing risk records, calculations and
tenant/role boundaries remain unchanged.

Revision ID: 0128
Revises: 0127
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0128"
down_revision: Union[str, None] = "0127"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = (
    ("risk_source", sa.String(250)),
    ("hazard_detail", sa.String(250)),
    ("potential_consequence", sa.Text()),
    ("legislation_basis", sa.Text()),
    ("responsible", sa.String(1000)),
    ("term_text", sa.String(250)),
    ("source_pn", sa.String(40)),
    ("source_photo_no", sa.String(40)),
    ("source_sheet", sa.String(120)),
    ("source_row", sa.Integer()),
    ("source_file", sa.String(255)),
    ("source_fingerprint", sa.String(64)),
    ("source_risk_score", sa.Float()),
)


def _index_names(bind, table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "risk_assessments" not in inspector.get_table_names():
        return

    existing = {item["name"] for item in inspector.get_columns("risk_assessments")}
    missing = [(name, column_type) for name, column_type in _COLUMNS if name not in existing]
    if missing:
        if bind.dialect.name == "postgresql":
            for name, column_type in missing:
                op.add_column("risk_assessments", sa.Column(name, column_type, nullable=True))
        else:
            with op.batch_alter_table("risk_assessments") as batch:
                for name, column_type in missing:
                    batch.add_column(sa.Column(name, column_type, nullable=True))

    if "ix_risk_assessments_source_fingerprint" not in _index_names(bind, "risk_assessments"):
        op.create_index(
            "ix_risk_assessments_source_fingerprint",
            "risk_assessments",
            ["source_fingerprint"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "risk_assessments" not in inspector.get_table_names():
        return

    if "ix_risk_assessments_source_fingerprint" in _index_names(bind, "risk_assessments"):
        op.drop_index("ix_risk_assessments_source_fingerprint", table_name="risk_assessments")

    existing = {item["name"] for item in sa.inspect(bind).get_columns("risk_assessments")}
    present = [name for name, _ in _COLUMNS if name in existing]
    if not present:
        return
    if bind.dialect.name == "postgresql":
        for name in present:
            op.drop_column("risk_assessments", name)
    else:
        with op.batch_alter_table("risk_assessments") as batch:
            for name in present:
                batch.drop_column(name)
