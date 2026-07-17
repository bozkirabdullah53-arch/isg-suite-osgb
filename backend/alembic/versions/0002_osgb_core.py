"""OSGB core hierarchy and assignments.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from app.core.database import Base
from app.models import entities  # noqa: F401

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}

def upgrade() -> None:
    bind = op.get_bind()
    for table_name in ("osgb_organizations", "isg_professionals", "workplace_assignments", "service_contracts"):
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)
    if "osgb_id" not in _columns(bind, "companies"):
        with op.batch_alter_table("companies") as batch:
            batch.add_column(sa.Column("osgb_id", sa.Integer(), nullable=True))
            batch.create_index("ix_companies_osgb_id", ["osgb_id"])
            batch.create_foreign_key("fk_companies_osgb_id", "osgb_organizations", ["osgb_id"], ["id"])
    if "osgb_id" not in _columns(bind, "users"):
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("osgb_id", sa.Integer(), nullable=True))
            batch.create_index("ix_users_osgb_id", ["osgb_id"])
            batch.create_foreign_key("fk_users_osgb_id", "osgb_organizations", ["osgb_id"], ["id"])

def downgrade() -> None:
    bind = op.get_bind()
    if "osgb_id" in _columns(bind, "users"):
        with op.batch_alter_table("users") as batch:
            batch.drop_column("osgb_id")
    if "osgb_id" in _columns(bind, "companies"):
        with op.batch_alter_table("companies") as batch:
            batch.drop_column("osgb_id")
    for table_name in ("service_contracts", "workplace_assignments", "isg_professionals", "osgb_organizations"):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
