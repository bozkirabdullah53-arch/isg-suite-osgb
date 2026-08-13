"""Complete the sector repair for catalog-derived remote programs.

Migration 0093 repaired the first four catalog packages.  The catalog has
since grown, so this follow-up covers the remaining sector-specific packages
without touching published, assigned, or manually edited programs.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0094_repair_catalog_sector2"
down_revision: Union[str, None] = "0093_repair_catalog_sector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PACKAGE_SECTOR_CODES = {
    "food-production-ohs": "food",
    "logistics-warehouse-transport-ohs": "logistics",
    "chemical-paint-production-ohs": "chemical",
    "open-mine-quarry-aggregate-ohs": "mining",
    "road-asphalt-infrastructure-ohs": "road",
    "office-general-ohs": "office",
    "working-at-height-ohs": "working_at_height",
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
    if not required.issubset(set(inspector.get_table_names())):
        return

    for catalog_code, sector_code in PACKAGE_SECTOR_CODES.items():
        program_filter = (
            "p.source_catalog_code = :catalog_code "
            "AND p.status IN ('draft', 'ready_for_review') "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM remote_training_assignments a "
            "  WHERE a.program_id = p.id"
            ") "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM remote_training_sections edited "
            "  WHERE edited.program_id = p.id "
            "    AND edited.status = 'active' "
            "    AND edited.sector_code <> 'common'"
            ")"
        )
        bind.execute(
            sa.text(
                "UPDATE remote_training_program_sectors "
                "SET is_enabled = (sector_code = :sector_code) "
                "WHERE program_id IN ("
                "  SELECT p.id FROM remote_training_programs p WHERE "
                + program_filter
                + ")"
            ),
            {"catalog_code": catalog_code, "sector_code": sector_code},
        )
        bind.execute(
            sa.text(
                "UPDATE remote_training_sections "
                "SET sector_code = :sector_code "
                "WHERE sector_code = 'common' "
                "AND program_id IN ("
                "  SELECT p.id FROM remote_training_programs p WHERE "
                + program_filter
                + ")"
            ),
            {"catalog_code": catalog_code, "sector_code": sector_code},
        )


def downgrade() -> None:
    # Do not overwrite a manager's deliberate edits during a rollback.
    pass
