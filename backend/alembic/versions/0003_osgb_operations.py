"""OSGB operations, CRM and finance.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union
from alembic import op
from app.core.database import Base
from app.models import entities  # noqa: F401

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    bind = op.get_bind()
    for table_name in ("service_visits", "crm_leads", "finance_transactions"):
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)

def downgrade() -> None:
    bind = op.get_bind()
    for table_name in ("finance_transactions", "crm_leads", "service_visits"):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
