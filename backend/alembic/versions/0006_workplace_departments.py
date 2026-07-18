"""Workplace departments for risk assessments.
Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.core.database import Base
from app.models import entities  # noqa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.tables["workplace_departments"].create(bind=bind, checkfirst=True)
    # SQLite/Postgres: add department_id if missing
    try:
        op.add_column("risk_assessments", sa.Column("department_id", sa.Integer(), nullable=True))
    except Exception:
        pass
    try:
        op.create_foreign_key(
            "fk_risk_assessments_department_id",
            "risk_assessments",
            "workplace_departments",
            ["department_id"],
            ["id"],
        )
    except Exception:
        pass
    try:
        op.create_index("ix_risk_assessments_department_id", "risk_assessments", ["department_id"])
    except Exception:
        pass


def downgrade():
    bind = op.get_bind()
    try:
        op.drop_constraint("fk_risk_assessments_department_id", "risk_assessments", type_="foreignkey")
    except Exception:
        pass
    try:
        op.drop_index("ix_risk_assessments_department_id", table_name="risk_assessments")
    except Exception:
        pass
    try:
        op.drop_column("risk_assessments", "department_id")
    except Exception:
        pass
    Base.metadata.tables["workplace_departments"].drop(bind=bind, checkfirst=True)
