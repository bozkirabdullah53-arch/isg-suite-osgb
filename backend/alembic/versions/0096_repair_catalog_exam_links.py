"""Remove incompatible question links from unassigned catalog snapshots."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0096_repair_catalog_exam_links"
down_revision: Union[str, None] = "0095_repair_existing_catalog_scope"
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
        "remote_training_assignments",
        "remote_training_program_questions",
        "remote_training_catalog_packages",
        "training_question_scopes",
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
            "AND NOT EXISTS (SELECT 1 FROM remote_training_assignments a WHERE a.program_id = p.id)"
        )
        if sector_code == "common":
            incompatible = (
                "NOT EXISTS (SELECT 1 FROM training_question_scopes qs "
                "WHERE qs.question_id = remote_training_program_questions.question_id "
                "AND qs.scope_type = 'common' "
                "AND COALESCE(qs.scope_value, '*') IN ('', '*'))"
            )
        else:
            incompatible = (
                "NOT EXISTS (SELECT 1 FROM training_question_scopes qs "
                "WHERE qs.question_id = remote_training_program_questions.question_id "
                "AND qs.scope_type <> 'common')"
            )
        bind.execute(
            sa.text(
                "DELETE FROM remote_training_program_questions "
                "WHERE remote_training_program_questions.program_id IN ("
                "SELECT p.id FROM remote_training_programs p WHERE "
                + program_filter + ") AND (" + incompatible
                + " OR COALESCE(remote_training_program_questions.sector_code, '') <> :sector_code)"
            ),
            {"catalog_code": catalog_code, "sector_code": sector_code},
        )


def downgrade() -> None:
    pass
