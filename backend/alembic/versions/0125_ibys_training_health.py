"""İBYS training instructor identity + structured occupational health fields.

Revision ID: 0125
Revises: 0124
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0125"
down_revision: Union[str, None] = "0124"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HEALTH_COLUMNS = (
    ("diagnosis", sa.Text()),
    ("laboratory_result_summary", sa.Text()),
    ("anamnesis_chronic_diseases", sa.Text()),
    ("anamnesis_past_medical_history", sa.Text()),
    ("anamnesis_family_history", sa.Text()),
    ("anamnesis_current_medications", sa.Text()),
    ("anamnesis_allergies", sa.Text()),
    ("anamnesis_smoking_status", sa.String(length=40)),
    ("anamnesis_smoking_pack_years", sa.Float()),
    ("anamnesis_alcohol_use", sa.String(length=80)),
    ("anamnesis_occupational_history", sa.Text()),
    ("anamnesis_previous_exposures", sa.Text()),
    ("anamnesis_current_complaints", sa.Text()),
)


def _enable_professional_identity_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    unset = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
    bypass = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
    current_osgb = "NULLIF(current_setting('app.current_osgb_id', true), '')::integer"
    scope = f"({unset}) OR ({bypass}) OR (osgb_id = {current_osgb})"
    op.execute('ALTER TABLE "professional_regulatory_identities" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "professional_regulatory_identities" FORCE ROW LEVEL SECURITY')
    op.execute(
        'DROP POLICY IF EXISTS "professional_regulatory_identities_osgb_scope" '
        'ON "professional_regulatory_identities"'
    )
    op.execute(
        'CREATE POLICY "professional_regulatory_identities_osgb_scope" '
        'ON "professional_regulatory_identities" '
        f"FOR ALL USING ({scope}) WITH CHECK ({scope})"
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "professional_regulatory_identities" not in tables:
        op.create_table(
            "professional_regulatory_identities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "osgb_id",
                sa.Integer(),
                sa.ForeignKey("osgb_organizations.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "professional_id",
                sa.Integer(),
                sa.ForeignKey("isg_professionals.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("identity_type", sa.String(20), nullable=False, server_default="tckn"),
            sa.Column("masked_value", sa.String(32), nullable=False),
            sa.Column("ciphertext", sa.Text(), nullable=False),
            sa.Column("lookup_hash", sa.String(64), nullable=False),
            sa.Column("encryption_version", sa.String(24), nullable=False, server_default="rid:v1"),
            sa.Column(
                "verified_by_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("verified_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint(
                "professional_id",
                "identity_type",
                name="uq_prof_reg_identity_professional_type",
            ),
            sa.UniqueConstraint(
                "osgb_id",
                "identity_type",
                "lookup_hash",
                name="uq_prof_reg_identity_osgb_lookup",
            ),
        )
        op.create_index(
            "ix_prof_reg_identity_osgb",
            "professional_regulatory_identities",
            ["osgb_id"],
        )
        op.create_index(
            "ix_prof_reg_identity_professional",
            "professional_regulatory_identities",
            ["professional_id"],
        )
        op.create_index(
            "ix_prof_reg_identity_lookup",
            "professional_regulatory_identities",
            ["lookup_hash"],
        )
        _enable_professional_identity_rls()

    inspector = sa.inspect(bind)
    if "training_sessions" in inspector.get_table_names():
        columns = {item["name"] for item in inspector.get_columns("training_sessions")}
        if "instructor_professional_id" not in columns:
            with op.batch_alter_table("training_sessions") as batch:
                batch.add_column(sa.Column("instructor_professional_id", sa.Integer(), nullable=True))
                batch.create_foreign_key(
                    "fk_training_sessions_instructor_professional",
                    "isg_professionals",
                    ["instructor_professional_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
                batch.create_index(
                    "ix_training_sessions_instructor_professional_id",
                    ["instructor_professional_id"],
                )

    inspector = sa.inspect(bind)
    if "health_records" in inspector.get_table_names():
        columns = {item["name"] for item in inspector.get_columns("health_records")}
        missing = [(name, type_) for name, type_ in _HEALTH_COLUMNS if name not in columns]
        if missing:
            with op.batch_alter_table("health_records") as batch:
                for name, type_ in missing:
                    batch.add_column(sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "health_records" in inspector.get_table_names():
        columns = {item["name"] for item in inspector.get_columns("health_records")}
        present = [name for name, _ in _HEALTH_COLUMNS if name in columns]
        if present:
            with op.batch_alter_table("health_records") as batch:
                for name in reversed(present):
                    batch.drop_column(name)

    inspector = sa.inspect(bind)
    if "training_sessions" in inspector.get_table_names():
        columns = {item["name"] for item in inspector.get_columns("training_sessions")}
        if "instructor_professional_id" in columns:
            foreign_keys = [
                item
                for item in inspector.get_foreign_keys("training_sessions")
                if item.get("constrained_columns") == ["instructor_professional_id"]
            ]
            indexes = {
                item.get("name")
                for item in inspector.get_indexes("training_sessions")
                if item.get("name")
                and item.get("column_names") == ["instructor_professional_id"]
            }
            with op.batch_alter_table("training_sessions") as batch:
                for index_name in sorted(indexes):
                    batch.drop_index(index_name)
                for fk in foreign_keys:
                    if fk.get("name"):
                        batch.drop_constraint(str(fk["name"]), type_="foreignkey")
                batch.drop_column("instructor_professional_id")

    inspector = sa.inspect(bind)
    if "professional_regulatory_identities" in inspector.get_table_names():
        if bind.dialect.name == "postgresql":
            op.execute(
                'DROP POLICY IF EXISTS "professional_regulatory_identities_osgb_scope" '
                'ON "professional_regulatory_identities"'
            )
        op.drop_table("professional_regulatory_identities")
