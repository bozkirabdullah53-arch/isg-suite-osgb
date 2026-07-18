"""Training session columns for document parity.
Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLS = (
    ("workplace_physician", sa.String(160)),
    ("employer_representative", sa.String(160)),
    ("logo_path", sa.String(500)),
    ("stamp_text", sa.String(220)),
)


def upgrade():
    for name, coltype in COLS:
        try:
            op.add_column("training_sessions", sa.Column(name, coltype(), nullable=True))
        except Exception:
            pass


def downgrade():
    for name, _ in reversed(COLS):
        try:
            op.drop_column("training_sessions", name)
        except Exception:
            pass
