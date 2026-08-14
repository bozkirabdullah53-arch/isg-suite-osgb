"""Repair stale scope rows on existing catalog-derived company programs."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0095_catalog_scope_repair"
down_revision: Union[str, None] = "0094_repair_catalog_sector2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PACKAGE_SECTOR_CODES = {
    "common-basic-ohs": "common",
    "construction-ohs": "construction",
    "metal-machine-ohs": "metal",
    "battery-production-ohs": "battery",
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
        "remote_training_catalog_packages",
    }
    if not required.issubset(set(inspector.get_table_names())):
        return

    for catalog_code, sector_code in PACKAGE_SECTOR_CODES.items():
        program_filter = (
            "p.status IN ('draft', 'ready_for_review') "
            "AND (p.source_catalog_code = :catalog_code OR EXISTS ("
            "  SELECT 1 FROM remote_training_catalog_packages cp "
            "  WHERE cp.id = p.source_catalog_package_id AND cp.code = :catalog_code"
            ")) "
            "AND NOT EXISTS (SELECT 1 FROM remote_training_assignments a WHERE a.program_id = p.id) "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM remote_training_sections edited "
            "  WHERE edited.program_id = p.id AND edited.status = 'active' "
            "    AND edited.sector_code NOT IN ('common', :sector_code)"
            ")"
        )
        params = {"catalog_code": catalog_code, "sector_code": sector_code}
        bind.execute(
            sa.text(
                "UPDATE remote_training_program_sectors "
                "SET is_enabled = (sector_code = :sector_code) "
                "WHERE program_id IN (SELECT p.id FROM remote_training_programs p WHERE "
                + program_filter + ")"
            ),
            params,
        )
        bind.execute(
            sa.text(
                "UPDATE remote_training_sections SET sector_code = :sector_code "
                "WHERE sector_code = 'common' AND program_id IN ("
                "SELECT p.id FROM remote_training_programs p WHERE "
                + program_filter + ")"
            ),
            params,
        )


def downgrade() -> None:
    pass
