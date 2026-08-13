"""Repair sector labels on unassigned catalog-derived company programs.

The central catalog originally copied every section into a company program
with ``sector_code='common'``.  This additive, idempotent repair updates only
draft/review snapshots with no employee assignments.  Published, assigned,
and historical records are deliberately left untouched.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0093_repair_catalog_sector"
down_revision: Union[str, None] = "0092_remote_ohs_strict"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PACKAGE_SECTOR_CODES = {
    "construction-ohs": "construction",
    "metal-machine-ohs": "metal",
    "battery-production-ohs": "battery",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    required = {
        "remote_training_programs",
        "remote_training_program_sectors",
        "remote_training_sections",
        "remote_training_assignments",
    }
    if not required.issubset({table["name"] for table in inspector.get_table_names()}):
        return

    for catalog_code, sector_code in PACKAGE_SECTOR_CODES.items():
        # Only repair snapshots that still have the original automatic shape:
        # all active sections were copied as ``common`` and no manager has
        # assigned anyone yet.  A manager who already retagged a section or
        # changed the scope is left completely untouched.
        bind.execute(
            sa.text(
                "UPDATE remote_training_program_sectors "
                "SET is_enabled = (sector_code = :sector_code) "
                "WHERE program_id IN ("
                "  SELECT p.id FROM remote_training_programs p "
                "  WHERE p.source_catalog_code = :catalog_code "
                "    AND p.status IN ('draft', 'ready_for_review') "
                "    AND NOT EXISTS ("
                "      SELECT 1 FROM remote_training_assignments a "
                "      WHERE a.program_id = p.id"
                "    ) "
                "    AND NOT EXISTS ("
                "      SELECT 1 FROM remote_training_sections s "
                "      WHERE s.program_id = p.id "
                "        AND s.status = 'active' "
                "        AND s.sector_code <> 'common'"
                "    )"
                ")"
            ),
            {"catalog_code": catalog_code, "sector_code": sector_code},
        )
        bind.execute(
            sa.text(
                "UPDATE remote_training_sections "
                "SET sector_code = :sector_code "
                "WHERE sector_code = 'common' "
                "AND program_id IN ("
                "  SELECT p.id FROM remote_training_programs p "
                "  WHERE p.source_catalog_code = :catalog_code "
                "    AND p.status IN ('draft', 'ready_for_review') "
                "    AND NOT EXISTS ("
                "      SELECT 1 FROM remote_training_assignments a "
                "      WHERE a.program_id = p.id"
                "    ) "
                "    AND NOT EXISTS ("
                "      SELECT 1 FROM remote_training_sections s "
                "      WHERE s.program_id = p.id "
                "        AND s.status = 'active' "
                "        AND s.sector_code <> 'common'"
                "    )"
                ")"
            ),
            {"catalog_code": catalog_code, "sector_code": sector_code},
        )


def downgrade() -> None:
    # Never reverse section labels automatically: doing so could overwrite a
    # manager's deliberate correction after deployment.  The migration is
    # intentionally forward-only and the original records remain intact.
    pass
