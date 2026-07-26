"""Risk revisions + media Pro parity (file_type, size, description, dof_id).

Revision ID: 0057
Revises: 0056
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0057"
down_revision: Union[str, None] = "0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("risk_revisions"):
        op.create_table(
            "risk_revisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("risk_id", sa.Integer(), nullable=False),
            sa.Column("revision_no", sa.Integer(), nullable=False),
            sa.Column("changed_by_id", sa.Integer(), nullable=True),
            sa.Column("changed_at", sa.DateTime(), nullable=True),
            sa.Column("field_name", sa.String(100), nullable=True),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("change_reason", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["risk_id"], ["risk_assessments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
        )
        op.create_index("ix_risk_revisions_risk_id", "risk_revisions", ["risk_id"])

    if insp.has_table("risk_media"):
        cols = {c["name"] for c in insp.get_columns("risk_media")}
        if "file_type" not in cols:
            op.add_column("risk_media", sa.Column("file_type", sa.String(20), nullable=True))
        if "file_size" not in cols:
            op.add_column("risk_media", sa.Column("file_size", sa.Integer(), nullable=True))
        if "description" not in cols:
            op.add_column("risk_media", sa.Column("description", sa.Text(), nullable=True))
        if "dof_id" not in cols:
            op.add_column("risk_media", sa.Column("dof_id", sa.Integer(), nullable=True))
            op.create_index("ix_risk_media_dof_id", "risk_media", ["dof_id"])
            try:
                op.create_foreign_key(
                    "fk_risk_media_dof_id",
                    "risk_media",
                    "risk_dofs",
                    ["dof_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                pass


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("risk_media"):
        cols = {c["name"] for c in insp.get_columns("risk_media")}
        if "dof_id" in cols:
            try:
                op.drop_constraint("fk_risk_media_dof_id", "risk_media", type_="foreignkey")
            except Exception:
                pass
            op.drop_index("ix_risk_media_dof_id", table_name="risk_media")
            op.drop_column("risk_media", "dof_id")
        for col in ("description", "file_size", "file_type"):
            if col in cols:
                op.drop_column("risk_media", col)
    if insp.has_table("risk_revisions"):
        op.drop_index("ix_risk_revisions_risk_id", table_name="risk_revisions")
        op.drop_table("risk_revisions")
