"""Widen health sensitive text columns for ciphertext.
Revision ID: 0037
Revises: 0036
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = (
    "summary",
    "confidential_note",
    "audiometry_result",
    "spirometry_result",
    "chest_xray_result",
    "suggested_tests",
    "exposures",
    "follow_up_note",
    "other_biological_test",
)


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("health_records"):
        return
    existing = {c["name"] for c in insp.get_columns("health_records")}
    with op.batch_alter_table("health_records") as batch:
        for col in _COLS:
            if col in existing:
                batch.alter_column(col, existing_type=sa.String(), type_=sa.Text(), existing_nullable=True)


def downgrade():
    # Text → String kısaltma veri kaybı riski; no-op
    pass
