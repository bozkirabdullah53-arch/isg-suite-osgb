"""Health records PRO parity columns and enum values.
Revision ID: 0012
Revises: 0011
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_COLS = (
    ("audiometry_date", sa.Date()),
    ("audiometry_result", sa.String(240)),
    ("spirometry_date", sa.Date()),
    ("spirometry_result", sa.String(240)),
    ("chest_xray_date", sa.Date()),
    ("chest_xray_result", sa.String(240)),
    ("blood_lead_date", sa.Date()),
    ("blood_lead_value", sa.Float()),
    ("blood_lead_unit", sa.String(20)),
    ("blood_lead_ref", sa.Float()),
    ("blood_lead_eval", sa.String(40)),
    ("suggested_tests", sa.String(1000)),
    ("exposures", sa.String(1000)),
    ("follow_up_note", sa.String(1500)),
    ("deleted_at", sa.DateTime()),
)

ENUM_VALUES = (
    ("healthrecordtype", (
        "return_exam", "job_change", "night_work", "heavy_hazardous", "other",
    )),
    ("healthfitnessstatus", ("tracking",)),
)


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("health_records"):
        return
    cols = {c["name"] for c in insp.get_columns("health_records")}
    for name, col in NEW_COLS:
        if name not in cols:
            op.add_column("health_records", sa.Column(name, col, nullable=True))
    for enum_name, values in ENUM_VALUES:
        for val in values:
            try:
                op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{val}'")
            except Exception:
                try:
                    op.execute(f"ALTER TYPE {enum_name} ADD VALUE '{val}'")
                except Exception:
                    pass


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("health_records"):
        return
    cols = {c["name"] for c in insp.get_columns("health_records")}
    for name, _ in reversed(NEW_COLS):
        if name in cols:
            op.drop_column("health_records", name)
