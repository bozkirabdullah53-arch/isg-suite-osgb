"""Restore approved shared catalog packages that still contain ready content.

Some ready packages were archived accidentally from the old catalog screen.  A
package is restored only when it is an official shared package and it still has
at least one active section with a current published video.  Empty drafts and
tenant-specific packages are left untouched.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0098_restore_shared_ready"
down_revision: Union[str, None] = "0097_shared_remote_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PACKAGE_CODES = (
    "common-basic-ohs",
    "construction-ohs",
    "metal-machine-ohs",
    "battery-production-ohs",
    "food-production-ohs",
    "logistics-warehouse-transport-ohs",
    "chemical-paint-production-ohs",
    "open-mine-quarry-aggregate-ohs",
    "road-asphalt-infrastructure-ohs",
    "office-general-ohs",
    "working-at-height-ohs",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    required = {
        "remote_training_catalog_packages",
        "remote_training_catalog_sections",
        "remote_training_catalog_videos",
    }
    if not required.issubset(tables):
        return

    bind.execute(
        sa.text(
            "UPDATE remote_training_catalog_packages AS p "
            "SET status = 'published', "
            "    published_at = COALESCE(p.published_at, p.updated_at, CURRENT_TIMESTAMP), "
            "    archived_at = NULL, "
            "    updated_at = CURRENT_TIMESTAMP "
            "WHERE p.osgb_id IS NULL "
            "  AND p.code IN :codes "
            "  AND p.status = 'archived' "
            "  AND EXISTS ("
            "      SELECT 1 "
            "      FROM remote_training_catalog_sections AS s "
            "      JOIN remote_training_catalog_videos AS v "
            "        ON v.section_id = s.id "
            "      WHERE s.package_id = p.id "
            "        AND s.status = 'active' "
            "        AND v.status = 'published' "
            "        AND v.is_current IS TRUE"
            "  )"
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": PACKAGE_CODES},
    )


def downgrade() -> None:
    # The previous status is not safely inferable after a shared rollout.
    pass
