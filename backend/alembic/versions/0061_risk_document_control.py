"""Add risk document control fields on companies (additive).

Revision ID: 0061
Revises: 0060
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0061"
down_revision: Union[str, None] = "0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    ("risk_method", sa.String(length=40)),
    ("risk_document_no", sa.String(length=80)),
    ("risk_revision_no", sa.String(length=20)),
    ("risk_revision_reason", sa.String(length=500)),
    ("risk_scope_note", sa.String(length=2000)),
)


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    for name, type_ in COLUMNS:
        if name not in cols:
            op.add_column("companies", sa.Column(name, type_, nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    for name, _ in reversed(COLUMNS):
        if name in cols:
            op.drop_column("companies", name)
