"""Advanced training module.
Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union
from alembic import op
from app.core.database import Base
from app.models import entities  # noqa
revision: str="0004"
down_revision: Union[str,None]="0003"
branch_labels: Union[str,Sequence[str],None]=None
depends_on: Union[str,Sequence[str],None]=None
def upgrade():
    bind=op.get_bind()
    for name in ("training_sessions","training_participants"):
        Base.metadata.tables[name].create(bind=bind,checkfirst=True)
def downgrade():
    bind=op.get_bind()
    for name in ("training_participants","training_sessions"):
        Base.metadata.tables[name].drop(bind=bind,checkfirst=True)
