"""Add offline field inspection context and media metadata."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0103_field_inspection_context"
down_revision: Union[str, None] = "0102_notification_completion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _names(inspector, table: str) -> set[str]:
    indexes = {item.get("name") for item in inspector.get_indexes(table)}
    constraints = {item.get("name") for item in inspector.get_unique_constraints(table)}
    return {name for name in indexes | constraints if name}


def _add_column(bind, table: str, column: sa.Column) -> None:
    inspector = sa.inspect(bind)
    if inspector.has_table(table):
        columns = {item["name"] for item in inspector.get_columns(table)}
        if column.name not in columns:
            op.add_column(table, column)


def _add_unique_index(bind, table: str, name: str, columns: list[str]) -> None:
    inspector = sa.inspect(bind)
    if inspector.has_table(table) and name not in _names(inspector, table):
        op.create_index(name, table, columns, unique=True)


def upgrade() -> None:
    bind = op.get_bind()
    _add_column(bind, "risk_assessments", sa.Column("record_origin", sa.String(30), nullable=True))
    _add_column(bind, "risk_assessments", sa.Column("client_reference", sa.String(80), nullable=True))
    _add_column(bind, "risk_assessments", sa.Column("observed_at", sa.DateTime(), nullable=True))
    _add_column(bind, "risk_assessments", sa.Column("observation_location", sa.String(220), nullable=True))
    _add_column(bind, "risk_assessments", sa.Column("gps_lat", sa.Float(), nullable=True))
    _add_column(bind, "risk_assessments", sa.Column("gps_lng", sa.Float(), nullable=True))
    _add_column(bind, "risk_assessments", sa.Column("gps_accuracy_m", sa.Float(), nullable=True))

    _add_column(bind, "risk_dofs", sa.Column("client_reference", sa.String(80), nullable=True))

    _add_column(bind, "risk_media", sa.Column("client_reference", sa.String(80), nullable=True))
    _add_column(bind, "risk_media", sa.Column("captured_at", sa.DateTime(), nullable=True))
    _add_column(bind, "risk_media", sa.Column("gps_lat", sa.Float(), nullable=True))
    _add_column(bind, "risk_media", sa.Column("gps_lng", sa.Float(), nullable=True))
    _add_column(bind, "risk_media", sa.Column("gps_accuracy_m", sa.Float(), nullable=True))

    inspector = sa.inspect(bind)
    if inspector.has_table("risk_assessments"):
        bind.execute(
            sa.text(
                "UPDATE risk_assessments SET record_origin = 'risk' "
                "WHERE record_origin IS NULL"
            )
        )
    _add_unique_index(bind, "risk_assessments", "uq_risk_company_client_reference", ["company_id", "client_reference"])
    _add_unique_index(bind, "risk_dofs", "uq_risk_dof_client_reference", ["risk_id", "client_reference"])
    _add_unique_index(bind, "risk_media", "uq_risk_media_client_reference", ["risk_id", "client_reference"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, name in (
        ("risk_assessments", "uq_risk_company_client_reference"),
        ("risk_dofs", "uq_risk_dof_client_reference"),
        ("risk_media", "uq_risk_media_client_reference"),
    ):
        if not inspector.has_table(table):
            continue
        constraints = {item.get("name") for item in inspector.get_unique_constraints(table)}
        indexes = {item.get("name") for item in inspector.get_indexes(table)}
        if name in constraints:
            op.drop_constraint(name, table_name=table, type_="unique")
        elif name in indexes:
            op.drop_index(name, table_name=table)
    for table, columns in (
        ("risk_media", ("gps_accuracy_m", "gps_lng", "gps_lat", "captured_at", "client_reference")),
        ("risk_dofs", ("client_reference",)),
        ("risk_assessments", ("gps_accuracy_m", "gps_lng", "gps_lat", "observation_location", "observed_at", "client_reference", "record_origin")),
    ):
        if inspector.has_table(table):
            present = {item["name"] for item in sa.inspect(bind).get_columns(table)}
            for name in columns:
                if name in present:
                    op.drop_column(table, name)
