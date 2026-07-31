"""Annual eval revision snapshots.
Revision ID: 0035
Revises: 0034
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("annual_plan_eval_revisions"):
        return
    op.create_table(
        "annual_plan_eval_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("annual_plan_evaluations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("snapshot_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("changes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("evaluation_id", "revision_no", name="uq_annual_eval_revision_no"),
    )
    op.create_index("ix_annual_plan_eval_revisions_evaluation_id", "annual_plan_eval_revisions", ["evaluation_id"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("annual_plan_eval_revisions"):
        return
    op.drop_index("ix_annual_plan_eval_revisions_evaluation_id", table_name="annual_plan_eval_revisions")
    op.drop_table("annual_plan_eval_revisions")
