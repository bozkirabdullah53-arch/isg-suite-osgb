"""Promote the existing ready remote catalog into the shared EİSA catalog.

The first catalog rollout created the approved packages under the first OSGB
scope.  Their company snapshots already own copied rows, so changing only the
catalog package scope cannot alter assignments, progress or certificates.
Future OSGB-specific changes are made through an explicit package fork.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0097_shared_remote_catalog"
down_revision: Union[str, None] = "0097_remote_auto_exam"
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
    if "remote_training_catalog_packages" not in inspector.get_table_names():
        return

    # Keep an already-existing global package if an installation has one.
    # Otherwise promote the most recently revised published package for each
    # approved code.  No catalog rows are deleted or copied.
    for code in PACKAGE_CODES:
        has_global = bind.execute(
            sa.text(
                "SELECT 1 FROM remote_training_catalog_packages "
                "WHERE code = :code AND osgb_id IS NULL LIMIT 1"
            ),
            {"code": code},
        ).first()
        if has_global:
            continue
        candidate = bind.execute(
            sa.text(
                "SELECT id FROM remote_training_catalog_packages "
                "WHERE code = :code "
                "ORDER BY CASE WHEN status = 'published' THEN 0 ELSE 1 END, "
                "revision_no DESC, updated_at DESC, id DESC LIMIT 1"
            ),
            {"code": code},
        ).first()
        if candidate:
            bind.execute(
                sa.text(
                    "UPDATE remote_training_catalog_packages "
                    "SET osgb_id = NULL WHERE id = :package_id"
                ),
                {"package_id": int(candidate[0])},
            )


def downgrade() -> None:
    # The previous tenant owner is not safely inferable from the catalog row
    # after a shared deployment; never move a package back automatically.
    pass
