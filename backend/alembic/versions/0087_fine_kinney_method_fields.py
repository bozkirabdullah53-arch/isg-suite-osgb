"""Add method-aware Fine-Kinney fields without rewriting legacy 5x5 data.

Revision ID: 0087_fine_kinney_method_fields
Revises: 0086_health_clinical_p0
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0087_fine_kinney_method_fields"
down_revision: Union[str, None] = "0086_health_clinical_p0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_COLUMNS = (
    ("method_code", sa.String(length=40), False, "5x5_l"),
    ("frequency", sa.Float(), True, None),
    ("residual_probability", sa.Float(), True, None),
    ("residual_frequency", sa.Float(), True, None),
    ("residual_severity", sa.Float(), True, None),
    ("residual_score", sa.Float(), True, None),
    ("residual_level", sa.String(length=50), True, None),
)


def _risk_table_exists() -> bool:
    return sa.inspect(op.get_bind()).has_table("risk_assessments")


def upgrade() -> None:
    if not _risk_table_exists():
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("risk_assessments")}
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # SQLite needs batch recreation for type changes and keeps the existing
        # risk indexes/constraints in the recreated table.
        with op.batch_alter_table("risk_assessments", recreate="always") as batch:
            for name, type_, nullable, default in NEW_COLUMNS:
                if name not in columns:
                    batch.add_column(
                        sa.Column(name, type_, nullable=nullable, server_default=default)
                    )
            if "probability" in columns:
                batch.alter_column(
                    "probability",
                    existing_type=sa.Integer(),
                    type_=sa.Float(),
                    existing_nullable=False,
                )
            if "severity" in columns:
                batch.alter_column(
                    "severity",
                    existing_type=sa.Integer(),
                    type_=sa.Float(),
                    existing_nullable=False,
                )
            if "risk_score" in columns:
                batch.alter_column(
                    "risk_score",
                    existing_type=sa.Integer(),
                    type_=sa.Float(),
                    existing_nullable=False,
                )
    else:
        for name, type_, nullable, default in NEW_COLUMNS:
            if name not in columns:
                op.add_column(
                    "risk_assessments",
                    sa.Column(name, type_, nullable=nullable, server_default=default),
                )
        for name in ("probability", "severity", "risk_score"):
            if name in columns:
                op.alter_column(
                    "risk_assessments",
                    name,
                    existing_type=sa.Integer(),
                    type_=sa.Float(),
                    existing_nullable=False,
                )

    # Explicitly normalize pre-existing and any nullable legacy rows.  The
    # method column is the source of truth for interpreting the factors.
    op.execute(
        sa.text(
            "UPDATE risk_assessments SET method_code = '5x5_l' "
            "WHERE method_code IS NULL OR trim(method_code) = ''"
        )
    )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("risk_assessments")}
    if "ix_risk_assessments_method_code" not in indexes:
        op.create_index(
            "ix_risk_assessments_method_code",
            "risk_assessments",
            ["method_code"],
            unique=False,
        )


def downgrade() -> None:
    if not _risk_table_exists():
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("risk_assessments")}
    indexes = {index["name"] for index in inspector.get_indexes("risk_assessments")}
    if "ix_risk_assessments_method_code" in indexes:
        op.drop_index("ix_risk_assessments_method_code", table_name="risk_assessments")

    drop_names = [name for name, _, _, _ in NEW_COLUMNS if name in columns]
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("risk_assessments", recreate="always") as batch:
            for name in reversed(drop_names):
                batch.drop_column(name)
            if "probability" in columns:
                batch.alter_column(
                    "probability",
                    existing_type=sa.Float(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                )
            if "severity" in columns:
                batch.alter_column(
                    "severity",
                    existing_type=sa.Float(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                )
            if "risk_score" in columns:
                batch.alter_column(
                    "risk_score",
                    existing_type=sa.Float(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                )
    else:
        for name in reversed(drop_names):
            op.drop_column("risk_assessments", name)
        for name in ("probability", "severity", "risk_score"):
            if name in columns:
                op.alter_column(
                    "risk_assessments",
                    name,
                    existing_type=sa.Float(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                )
