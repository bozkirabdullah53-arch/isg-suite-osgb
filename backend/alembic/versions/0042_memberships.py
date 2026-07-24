"""Organization / workplace membership tables (P1-04).
Revision ID: 0042
Revises: 0041
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("organization_memberships"):
        op.create_table(
            "organization_memberships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "osgb_id",
                sa.Integer(),
                sa.ForeignKey("osgb_organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(length=40), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", "osgb_id", "role", name="uq_org_membership_user_osgb_role"),
        )
        op.create_index("ix_organization_memberships_user_id", "organization_memberships", ["user_id"])
        op.create_index("ix_organization_memberships_osgb_id", "organization_memberships", ["osgb_id"])

    if not insp.has_table("workplace_memberships"):
        op.create_table(
            "workplace_memberships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "company_id",
                sa.Integer(),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(length=40), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "user_id", "company_id", "role", name="uq_wp_membership_user_company_role"
            ),
        )
        op.create_index("ix_workplace_memberships_user_id", "workplace_memberships", ["user_id"])
        op.create_index("ix_workplace_memberships_company_id", "workplace_memberships", ["company_id"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("workplace_memberships"):
        op.drop_table("workplace_memberships")
    if insp.has_table("organization_memberships"):
        op.drop_table("organization_memberships")
