"""Assignment/visit file columns, health report parity, training stamp width.

Revision ID: 0015
Revises: 0014
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_cols(table: str, specs: tuple[tuple[str, sa.types.TypeEngine], ...]) -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return
    cols = {c["name"] for c in insp.get_columns(table)}
    for name, coltype in specs:
        if name not in cols:
            op.add_column(table, sa.Column(name, coltype, nullable=True))


def upgrade():
    _add_cols(
        "workplace_assignments",
        (
            ("contract_file_name", sa.String(255)),
            ("contract_storage_path", sa.String(500)),
            ("contract_content_type", sa.String(120)),
        ),
    )
    _add_cols(
        "service_visits",
        (
            ("notebook_file_name", sa.String(255)),
            ("notebook_storage_path", sa.String(500)),
            ("notebook_content_type", sa.String(120)),
        ),
    )
    _add_cols(
        "health_records",
        (
            ("other_biological_test", sa.String(1000)),
            ("report_file_name", sa.String(255)),
            ("report_storage_path", sa.String(500)),
            ("report_content_type", sa.String(120)),
        ),
    )

    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("training_sessions"):
        cols = {c["name"] for c in insp.get_columns("training_sessions")}
        if "stamp_text" in cols:
            try:
                op.alter_column(
                    "training_sessions",
                    "stamp_text",
                    existing_type=sa.String(220),
                    type_=sa.String(400),
                    existing_nullable=True,
                )
            except Exception:
                try:
                    op.alter_column(
                        "training_sessions",
                        "stamp_text",
                        type_=sa.String(400),
                        existing_nullable=True,
                    )
                except Exception:
                    pass

    for enum_name, values in (
        ("healthfitnessstatus", ("fit", "conditional", "unfit", "pending")),
    ):
        from app.core.pg_enum import pg_add_enum_value

        for val in values:
            pg_add_enum_value(bind, enum_name, val)


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table, names in (
        ("health_records", ("report_content_type", "report_storage_path", "report_file_name", "other_biological_test")),
        ("service_visits", ("notebook_content_type", "notebook_storage_path", "notebook_file_name")),
        ("workplace_assignments", ("contract_content_type", "contract_storage_path", "contract_file_name")),
    ):
        if not insp.has_table(table):
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        for name in names:
            if name in cols:
                op.drop_column(table, name)
