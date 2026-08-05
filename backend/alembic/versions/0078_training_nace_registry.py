"""Versioned NACE training classification registry.

Revision ID: 0078_training_nace_registry
Revises: 0077_committee_approval
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0078_training_nace_registry"
down_revision: Union[str, None] = "0077_committee_approval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("training_nace_catalog_versions"):
        op.create_table(
            "training_nace_catalog_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("version_code", sa.String(80), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("source_label", sa.String(300), nullable=False),
            sa.Column("source_url", sa.String(1000), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="candidate"),
            sa.Column("entry_count", sa.Integer(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("activated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("activated_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "status IN ('candidate','active','retired')",
                name="ck_training_nace_catalog_version_status",
            ),
            sa.CheckConstraint("entry_count >= 0", name="ck_training_nace_catalog_entry_count"),
            sa.UniqueConstraint("content_hash", name="uq_training_nace_catalog_content_hash"),
        )
        op.create_index(
            "ix_training_nace_catalog_versions_status",
            "training_nace_catalog_versions",
            ["status"],
        )
        op.create_index(
            "ix_training_nace_catalog_versions_created_at",
            "training_nace_catalog_versions",
            ["created_at"],
        )

    if not inspector.has_table("training_nace_catalog_entries"):
        op.create_table(
            "training_nace_catalog_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "version_id",
                sa.Integer(),
                sa.ForeignKey("training_nace_catalog_versions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("nace_code", sa.String(10), nullable=False),
            sa.Column("nace_key", sa.String(20), nullable=False),
            sa.Column("description", sa.String(1000), nullable=False),
            sa.Column("division_code", sa.String(2), nullable=False),
            sa.Column("activity_group_code", sa.String(5), nullable=False),
            sa.Column("main_sector_code", sa.String(2), nullable=False),
            sa.Column("main_sector_name", sa.String(300), nullable=False),
            sa.Column("profile_code", sa.String(140), nullable=False),
            sa.Column("profile_name", sa.String(300), nullable=False),
            sa.Column("hazard_class", sa.String(30), nullable=False),
            sa.Column("risk_tags_json", sa.Text(), nullable=False),
            sa.Column("special_risks_json", sa.Text(), nullable=False),
            sa.Column("topics_json", sa.Text(), nullable=False),
            sa.Column("lesson_hours", sa.Integer(), nullable=False),
            sa.Column("instruction_minutes", sa.Integer(), nullable=False),
            sa.Column("scheduled_minutes", sa.Integer(), nullable=False),
            sa.Column("sector_lesson_hours", sa.Integer(), nullable=False),
            sa.Column("sector_instruction_minutes", sa.Integer(), nullable=False),
            sa.Column("sector_scheduled_minutes", sa.Integer(), nullable=False),
            sa.Column("mapping_status", sa.String(30), nullable=False),
            sa.Column("validation_errors_json", sa.Text(), nullable=False),
            sa.CheckConstraint(
                "hazard_class IN ('Az Tehlikeli','Tehlikeli','Çok Tehlikeli')",
                name="ck_training_nace_entry_hazard_class",
            ),
            sa.CheckConstraint(
                "mapping_status IN ('mapped','review_required','blocked')",
                name="ck_training_nace_entry_mapping_status",
            ),
            sa.CheckConstraint("lesson_hours > 0", name="ck_training_nace_entry_lesson_hours"),
            sa.CheckConstraint("instruction_minutes > 0", name="ck_training_nace_entry_instruction_minutes"),
            sa.CheckConstraint("scheduled_minutes > 0", name="ck_training_nace_entry_scheduled_minutes"),
            sa.UniqueConstraint("version_id", "nace_code", name="uq_training_nace_catalog_entry"),
        )
        op.create_index(
            "ix_training_nace_catalog_entries_version_id",
            "training_nace_catalog_entries",
            ["version_id"],
        )
        op.create_index(
            "ix_training_nace_catalog_entries_nace_code",
            "training_nace_catalog_entries",
            ["nace_code"],
        )
        op.create_index(
            "ix_training_nace_catalog_entries_profile_code",
            "training_nace_catalog_entries",
            ["profile_code"],
        )
        op.create_index(
            "ix_training_nace_catalog_entries_hazard_class",
            "training_nace_catalog_entries",
            ["hazard_class"],
        )
        op.create_index(
            "ix_training_nace_catalog_entries_mapping_status",
            "training_nace_catalog_entries",
            ["mapping_status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("training_nace_catalog_entries"):
        op.drop_table("training_nace_catalog_entries")
    if inspector.has_table("training_nace_catalog_versions"):
        op.drop_table("training_nace_catalog_versions")
