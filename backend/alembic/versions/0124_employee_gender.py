"""Add optional employee gender for auditable workforce summaries."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0124"
down_revision: Union[str, None] = "0123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {item["name"] for item in sa.inspect(bind).get_columns("employees")}
    if "gender" not in columns:
        op.add_column("employees", sa.Column("gender", sa.String(length=20), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {item["name"] for item in sa.inspect(bind).get_columns("employees")}
    if "gender" in columns:
        op.drop_column("employees", "gender")
