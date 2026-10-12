"""Add explicit OSGB grants for shared remote training packages."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0130"
down_revision = "0129"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "remote_training_catalog_package_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("osgb_id", sa.Integer(), nullable=False),
        sa.Column("granted_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["package_id"], ["remote_training_catalog_packages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["osgb_id"], ["osgb_organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("package_id", "osgb_id", name="uq_remote_catalog_package_grant"),
    )
    op.create_index("ix_remote_catalog_package_grants_osgb", "remote_training_catalog_package_grants", ["osgb_id"])
    op.create_index("ix_remote_catalog_package_grants_package", "remote_training_catalog_package_grants", ["package_id"])
    # Preserve the visibility existing tenants already had before explicit grants.
    op.execute(
        sa.text(
            """
            INSERT INTO remote_training_catalog_package_grants (package_id, osgb_id)
            SELECT p.id, o.id
            FROM remote_training_catalog_packages p
            CROSS JOIN osgb_organizations o
            WHERE p.osgb_id IS NULL
              AND p.status = 'published'
              AND o.is_active = TRUE
            """
        )
    )


def downgrade() -> None:
    op.drop_table("remote_training_catalog_package_grants")
