"""Add delayed to annualplanstatus enum (Postgres).
Revision ID: 0014
Revises: 0013
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Postgres only — SQLite stores enum as VARCHAR and does not need this.
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for value in ("delayed", "cancelled"):
        try:
            op.execute(f"ALTER TYPE annualplanstatus ADD VALUE IF NOT EXISTS '{value}'")
        except Exception:
            try:
                op.execute(f"ALTER TYPE annualplanstatus ADD VALUE '{value}'")
            except Exception:
                pass


def downgrade():
    # Postgres enum values cannot be removed safely; leave as no-op.
    pass
