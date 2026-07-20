"""Revision ID: 0016
Revises: 0015
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("osgb_applications"):
        op.create_table(
            "osgb_applications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(220), nullable=False),
            sa.Column("authorization_number", sa.String(80), nullable=False),
            sa.Column("tax_number", sa.String(20), nullable=False),
            sa.Column("responsible_manager", sa.String(160), nullable=True),
            sa.Column("contact_email", sa.String(255), nullable=False),
            sa.Column("contact_phone", sa.String(40), nullable=True),
            sa.Column("address", sa.String(500), nullable=True),
            sa.Column("applicant_name", sa.String(160), nullable=False),
            sa.Column("applicant_email", sa.String(255), nullable=False),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("matched_osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id"), nullable=True),
            sa.Column("auto_matched", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("rejection_reason", sa.String(500), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_osgb_applications_status", "osgb_applications", ["status"])
        op.create_index("ix_osgb_applications_authorization_number", "osgb_applications", ["authorization_number"])
        op.create_index("ix_osgb_applications_tax_number", "osgb_applications", ["tax_number"])

    if not insp.has_table("osgb_subscriptions"):
        op.create_table(
            "osgb_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id"), nullable=False, unique=True),
            sa.Column("plan", sa.String(20), nullable=False, server_default="standard"),
            sa.Column("status", sa.String(20), nullable=False, server_default="trial"),
            sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
            sa.Column("current_period_ends_at", sa.DateTime(), nullable=True),
            sa.Column("max_users", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("max_workplaces", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("last_payment_channel", sa.String(20), nullable=True),
            sa.Column("payment_notes", sa.String(1000), nullable=True),
            sa.Column("is_auto_renew", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_osgb_subscriptions_osgb_id", "osgb_subscriptions", ["osgb_id"])

    # Mevcut OSGB'lere deneme aboneliği (10 gün)
    if insp.has_table("osgb_organizations") and insp.has_table("osgb_subscriptions"):
        if bind.dialect.name == "sqlite":
            op.execute(
                sa.text(
                    """
                    INSERT INTO osgb_subscriptions (
                        osgb_id, plan, status, trial_ends_at, max_users, max_workplaces,
                        is_auto_renew, created_at, updated_at
                    )
                    SELECT o.id, 'standard', 'trial',
                           datetime('now', '+10 days'),
                           50, 100, 0, datetime('now'), datetime('now')
                    FROM osgb_organizations o
                    WHERE NOT EXISTS (
                        SELECT 1 FROM osgb_subscriptions s WHERE s.osgb_id = o.id
                    )
                    """
                )
            )
        else:
            op.execute(
                sa.text(
                    """
                    INSERT INTO osgb_subscriptions (
                        osgb_id, plan, status, trial_ends_at, max_users, max_workplaces,
                        is_auto_renew, created_at, updated_at
                    )
                    SELECT o.id, 'standard', 'trial',
                           NOW() + INTERVAL '10 days',
                           50, 100, false, NOW(), NOW()
                    FROM osgb_organizations o
                    WHERE NOT EXISTS (
                        SELECT 1 FROM osgb_subscriptions s WHERE s.osgb_id = o.id
                    )
                    """
                )
            )


def downgrade():
    op.drop_table("osgb_subscriptions")
    op.drop_table("osgb_applications")
