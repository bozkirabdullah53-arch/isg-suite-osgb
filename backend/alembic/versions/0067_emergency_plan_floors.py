"""Acil durum kroki — katlar + scene_json.

Revision ID: 0067
Revises: 0066
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0067"
down_revision: Union[str, None] = "0066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("emergency_plans"):
        cols = {c["name"] for c in insp.get_columns("emergency_plans")}
        if "locked_at" not in cols:
            op.add_column("emergency_plans", sa.Column("locked_at", sa.DateTime(), nullable=True))

    if not insp.has_table("emergency_plan_floors"):
        op.create_table(
            "emergency_plan_floors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("plan_id", sa.Integer(), sa.ForeignKey("emergency_plans.id"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("name", sa.String(120), nullable=False, server_default="Zemin"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("background_file_name", sa.String(255), nullable=True),
            sa.Column("background_storage_path", sa.String(500), nullable=True),
            sa.Column("scene_json", sa.Text(), nullable=True),
            sa.Column("width", sa.Integer(), nullable=False, server_default="1600"),
            sa.Column("height", sa.Integer(), nullable=False, server_default="1000"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_emergency_plan_floors_plan_id", "emergency_plan_floors", ["plan_id"])
        op.create_index("ix_emergency_plan_floors_company_id", "emergency_plan_floors", ["company_id"])

    # RLS (Postgres) — company scope
    if bind.dialect.name == "postgresql":
        scope = """
                  COALESCE(current_setting('app.current_user_id', true), '') = ''
                  OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                  OR (
                    COALESCE(current_setting('app.allowed_company_ids', true), '') <> ''
                    AND emergency_plan_floors.company_id = ANY (
                      string_to_array(current_setting('app.allowed_company_ids', true), ',')::integer[]
                    )
                  )
        """
        op.execute(sa.text("ALTER TABLE emergency_plan_floors ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE emergency_plan_floors FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"""
                DO $policy$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = current_schema()
                      AND tablename = 'emergency_plan_floors'
                      AND policyname = 'rls_emergency_plan_floors_company'
                  ) THEN
                    CREATE POLICY rls_emergency_plan_floors_company ON emergency_plan_floors
                      FOR ALL
                      USING ({scope})
                      WITH CHECK ({scope});
                  END IF;
                END
                $policy$;
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("emergency_plan_floors"):
        if bind.dialect.name == "postgresql":
            op.execute(sa.text("DROP POLICY IF EXISTS rls_emergency_plan_floors_company ON emergency_plan_floors"))
        op.drop_index("ix_emergency_plan_floors_company_id", table_name="emergency_plan_floors")
        op.drop_index("ix_emergency_plan_floors_plan_id", table_name="emergency_plan_floors")
        op.drop_table("emergency_plan_floors")
    if insp.has_table("emergency_plans"):
        cols = {c["name"] for c in insp.get_columns("emergency_plans")}
        if "locked_at" in cols:
            op.drop_column("emergency_plans", "locked_at")
