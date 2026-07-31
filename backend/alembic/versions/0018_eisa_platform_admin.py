"""EİSA platform billing, packages, notifications, audit extensions.

Revision ID: 0018
Revises: 0017
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("osgb_organizations"):
        cols = {c["name"] for c in insp.get_columns("osgb_organizations")}
        if "archived_at" not in cols:
            with op.batch_alter_table("osgb_organizations") as batch:
                batch.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))

    if insp.has_table("audit_logs"):
        cols = {c["name"] for c in insp.get_columns("audit_logs")}
        with op.batch_alter_table("audit_logs") as batch:
            if "module" not in cols:
                batch.add_column(sa.Column("module", sa.String(80), nullable=True))
            if "old_value" not in cols:
                batch.add_column(sa.Column("old_value", sa.Text(), nullable=True))
            if "new_value" not in cols:
                batch.add_column(sa.Column("new_value", sa.Text(), nullable=True))

    if not insp.has_table("eisa_packages"):
        op.create_table(
            "eisa_packages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(40), nullable=False, unique=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("description", sa.String(1000), nullable=True),
            sa.Column("price_monthly", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("price_yearly", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("max_users", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("max_workplaces", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_eisa_packages_code", "eisa_packages", ["code"])
        op.create_index("ix_eisa_packages_is_active", "eisa_packages", ["is_active"])

    if insp.has_table("osgb_subscriptions"):
        cols = {c["name"] for c in insp.get_columns("osgb_subscriptions")}
        if "package_id" not in cols:
            with op.batch_alter_table("osgb_subscriptions") as batch:
                batch.add_column(sa.Column("package_id", sa.Integer(), nullable=True))
                batch.create_foreign_key(
                    "fk_osgb_subscriptions_package_id",
                    "eisa_packages",
                    ["package_id"],
                    ["id"],
                )

    if not insp.has_table("eisa_subscription_payments"):
        op.create_table(
            "eisa_subscription_payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("reference_no", sa.String(80), nullable=False, unique=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id"), nullable=False),
            sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("osgb_subscriptions.id"), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(8), nullable=False, server_default="TRY"),
            sa.Column("payment_method", sa.String(20), nullable=True),
            sa.Column("payment_status", sa.String(20), nullable=False, server_default="completed"),
            sa.Column("payment_date", sa.DateTime(), nullable=False),
            sa.Column("description", sa.String(1000), nullable=True),
            sa.Column("period_start", sa.DateTime(), nullable=True),
            sa.Column("period_end", sa.DateTime(), nullable=True),
            sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_eisa_subscription_payments_osgb_id", "eisa_subscription_payments", ["osgb_id"])
        op.create_index("ix_eisa_subscription_payments_reference_no", "eisa_subscription_payments", ["reference_no"])

    if not insp.has_table("eisa_platform_notifications"):
        op.create_table(
            "eisa_platform_notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("channel", sa.String(20), nullable=False),
            sa.Column("target_scope", sa.String(20), nullable=False),
            sa.Column("target_osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id"), nullable=True),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("message", sa.String(2000), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    if not insp.has_table("eisa_platform_settings"):
        op.create_table(
            "eisa_platform_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(80), nullable=False, unique=True),
            sa.Column("value", sa.String(2000), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    # Varsayılan paket
    if bind.dialect.name == "sqlite":
        op.execute(
            sa.text(
                """
                INSERT INTO eisa_packages (
                    code, name, description, price_monthly, price_yearly,
                    max_users, max_workplaces, is_active, sort_order, created_at, updated_at
                )
                SELECT 'standard', 'Standart OSGB', 'Temel OSGB abonelik paketi',
                       0, 0, 50, 100, 1, 0, datetime('now'), datetime('now')
                WHERE NOT EXISTS (SELECT 1 FROM eisa_packages WHERE code = 'standard')
                """
            )
        )
    else:
        op.execute(
            sa.text(
                """
                INSERT INTO eisa_packages (
                    code, name, description, price_monthly, price_yearly,
                    max_users, max_workplaces, is_active, sort_order, created_at, updated_at
                )
                SELECT 'standard', 'Standart OSGB', 'Temel OSGB abonelik paketi',
                       0, 0, 50, 100, true, 0, NOW(), NOW()
                WHERE NOT EXISTS (SELECT 1 FROM eisa_packages WHERE code = 'standard')
                """
            )
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table in (
        "eisa_platform_settings",
        "eisa_platform_notifications",
        "eisa_subscription_payments",
    ):
        if insp.has_table(table):
            op.drop_table(table)

    if insp.has_table("osgb_subscriptions"):
        cols = {c["name"] for c in insp.get_columns("osgb_subscriptions")}
        if "package_id" in cols:
            with op.batch_alter_table("osgb_subscriptions") as batch:
                batch.drop_constraint("fk_osgb_subscriptions_package_id", type_="foreignkey")
                batch.drop_column("package_id")

    if insp.has_table("eisa_packages"):
        op.drop_table("eisa_packages")

    if insp.has_table("audit_logs"):
        cols = {c["name"] for c in insp.get_columns("audit_logs")}
        with op.batch_alter_table("audit_logs") as batch:
            if "new_value" in cols:
                batch.drop_column("new_value")
            if "old_value" in cols:
                batch.drop_column("old_value")
            if "module" in cols:
                batch.drop_column("module")

    if insp.has_table("osgb_organizations"):
        cols = {c["name"] for c in insp.get_columns("osgb_organizations")}
        if "archived_at" in cols:
            with op.batch_alter_table("osgb_organizations") as batch:
                batch.drop_column("archived_at")
