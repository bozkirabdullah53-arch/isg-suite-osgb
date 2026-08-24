"""Additive KKD stok, iade ve fire hareket defteri.

Revision ID: 0104_ppe_inventory_management
Revises: 0103_field_inspection_context

Mevcut ppe_assignments kayıtları korunur. inventory_item_id nullable'dır;
eski zimmet akışı stok kartı seçmeden çalışmaya devam eder.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0104_ppe_inventory_management"
down_revision: Union[str, None] = "0103_field_inspection_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table: str) -> bool:
    return sa.inspect(bind).has_table(table)


def _columns(bind, table: str) -> set[str]:
    if not _table_exists(bind, table):
        return set()
    return {item["name"] for item in sa.inspect(bind).get_columns(table)}


def _enable_rls(bind, table: str) -> None:
    if bind.dialect.name != "postgresql" or not _table_exists(bind, table):
        return
    policy = f"{table}_company_scope"
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            f"""
            DO $policy$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = current_schema()
                  AND tablename = '{table}'
                  AND policyname = '{policy}'
              ) THEN
                CREATE POLICY "{policy}" ON "{table}"
                  FOR ALL
                  USING (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                    OR (
                      COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                      AND "{table}".company_id = ANY (
                        string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                      )
                    )
                  )
                  WITH CHECK (
                    COALESCE(current_setting('app.current_user_id', true), '') = ''
                    OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                    OR (
                      COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                      AND "{table}".company_id = ANY (
                        string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                      )
                    )
                  );
              END IF;
            END
            $policy$;
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "ppe_inventory_items"):
        op.create_table(
            "ppe_inventory_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
            sa.Column("category", sa.String(120), nullable=False),
            sa.Column("item_type", sa.String(160), nullable=False),
            sa.Column("brand", sa.String(120), nullable=True),
            sa.Column("model", sa.String(120), nullable=True),
            sa.Column("size", sa.String(60), nullable=True),
            sa.Column("shelf_life_text", sa.String(120), nullable=True),
            sa.Column("expiry_date", sa.Date(), nullable=True),
            sa.Column("renewal_date", sa.Date(), nullable=True),
            sa.Column("min_stock", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("notes", sa.String(1000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_ppe_inventory_items_company_id", "ppe_inventory_items", ["company_id"])
        op.create_index("ix_ppe_inventory_items_item_type", "ppe_inventory_items", ["item_type"])
        op.create_index("ix_ppe_inventory_items_expiry_date", "ppe_inventory_items", ["expiry_date"])
        op.create_index("ix_ppe_inventory_items_renewal_date", "ppe_inventory_items", ["renewal_date"])
        op.create_index("ix_ppe_inventory_items_is_active", "ppe_inventory_items", ["is_active"])

    if _table_exists(bind, "ppe_assignments"):
        cols = _columns(bind, "ppe_assignments")
        if "inventory_item_id" not in cols:
            op.add_column(
                "ppe_assignments",
                sa.Column(
                    "inventory_item_id",
                    sa.Integer(),
                    sa.ForeignKey("ppe_inventory_items.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )
            op.create_index("ix_ppe_assignments_inventory_item_id", "ppe_assignments", ["inventory_item_id"])
        if "returned_quantity" not in cols:
            op.add_column(
                "ppe_assignments",
                sa.Column("returned_quantity", sa.Integer(), nullable=False, server_default="0"),
            )
        if "scrapped_quantity" not in cols:
            op.add_column(
                "ppe_assignments",
                sa.Column("scrapped_quantity", sa.Integer(), nullable=False, server_default="0"),
            )

    if not _table_exists(bind, "ppe_inventory_movements"):
        op.create_table(
            "ppe_inventory_movements",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "inventory_item_id",
                sa.Integer(),
                sa.ForeignKey("ppe_inventory_items.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "assignment_id",
                sa.Integer(),
                sa.ForeignKey("ppe_assignments.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("movement_type", sa.String(20), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("movement_date", sa.Date(), nullable=False),
            sa.Column("reason", sa.String(500), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_ppe_inventory_movements_company_id", "ppe_inventory_movements", ["company_id"])
        op.create_index("ix_ppe_inventory_movements_inventory_item_id", "ppe_inventory_movements", ["inventory_item_id"])
        op.create_index("ix_ppe_inventory_movements_assignment_id", "ppe_inventory_movements", ["assignment_id"])
        op.create_index("ix_ppe_inventory_movements_movement_type", "ppe_inventory_movements", ["movement_type"])
        op.create_index("ix_ppe_inventory_movements_movement_date", "ppe_inventory_movements", ["movement_date"])
        op.create_index("ix_ppe_inventory_movements_created_at", "ppe_inventory_movements", ["created_at"])

    _enable_rls(bind, "ppe_inventory_items")
    _enable_rls(bind, "ppe_inventory_movements")


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("ppe_inventory_movements", "ppe_inventory_items"):
        if bind.dialect.name == "postgresql" and _table_exists(bind, table):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_company_scope" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    if _table_exists(bind, "ppe_inventory_movements"):
        op.drop_table("ppe_inventory_movements")
    if _table_exists(bind, "ppe_assignments"):
        cols = _columns(bind, "ppe_assignments")
        if "scrapped_quantity" in cols:
            op.drop_column("ppe_assignments", "scrapped_quantity")
        if "returned_quantity" in cols:
            op.drop_column("ppe_assignments", "returned_quantity")
        if "inventory_item_id" in cols:
            op.drop_index("ix_ppe_assignments_inventory_item_id", table_name="ppe_assignments")
            op.drop_column("ppe_assignments", "inventory_item_id")
    if _table_exists(bind, "ppe_inventory_items"):
        op.drop_table("ppe_inventory_items")
