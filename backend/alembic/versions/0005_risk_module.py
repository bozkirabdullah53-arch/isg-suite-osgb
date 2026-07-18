"""Risk assessment module tables.
Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union
from alembic import op
from app.core.database import Base
from app.models import entities  # noqa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    for name in ("hazard_categories", "hazards", "risk_assessments", "risk_dofs"):
        Base.metadata.tables[name].create(bind=bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    for name in ("risk_dofs", "risk_assessments", "hazards", "hazard_categories"):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
