"""Stable catalog-section identity for materialized remote-training programs.

Revision ID: 0106_remote_catalog_section_links
Revises: 0105_visual_field_inspections

The migration is additive. Existing program/section/video/progress rows are not
rewritten. Links are backfilled only when both the catalog title and the copied
program title identify exactly one section; ambiguous legacy rows deliberately
remain unlinked and are resolved fail-closed by the application.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0106_remote_catalog_section_links"
down_revision: Union[str, None] = "0105_visual_field_inspections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "remote_training_catalog_section_links"):
        op.create_table(
            "remote_training_catalog_section_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "program_id",
                sa.Integer(),
                sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "program_section_id",
                sa.Integer(),
                sa.ForeignKey("remote_training_sections.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "catalog_package_id",
                sa.Integer(),
                sa.ForeignKey("remote_training_catalog_packages.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "catalog_section_id",
                sa.Integer(),
                sa.ForeignKey("remote_training_catalog_sections.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "program_id",
                "catalog_section_id",
                name="uq_remote_catalog_section_link_program_source",
            ),
            sa.UniqueConstraint(
                "program_section_id",
                name="uq_remote_catalog_section_link_program_section",
            ),
        )
        op.create_index(
            "ix_remote_catalog_section_links_program",
            "remote_training_catalog_section_links",
            ["program_id"],
        )
        op.create_index(
            "ix_remote_catalog_section_links_package",
            "remote_training_catalog_section_links",
            ["catalog_package_id"],
        )
        op.create_index(
            "ix_remote_catalog_section_links_source",
            "remote_training_catalog_section_links",
            ["catalog_section_id"],
        )

    required = {
        "remote_training_programs",
        "remote_training_sections",
        "remote_training_catalog_packages",
        "remote_training_catalog_sections",
        "remote_training_catalog_section_links",
    }
    if not all(_has_table(bind, table) for table in required):
        return

    # Never use order_index for historical identity.  Titles were copied at
    # materialization time, so an exact normalized title is safe only when it
    # is unique on both sides. Any ambiguous row stays unlinked instead of
    # risking a cross-section video move.
    bind.execute(sa.text("""
        INSERT INTO remote_training_catalog_section_links
            (program_id, program_section_id, catalog_package_id, catalog_section_id, created_at)
        SELECT
            p.id,
            s.id,
            cp.id,
            cs.id,
            CURRENT_TIMESTAMP
        FROM remote_training_programs AS p
        JOIN remote_training_sections AS s
          ON s.program_id = p.id
        JOIN remote_training_catalog_packages AS cp
          ON cp.id = p.source_catalog_package_id
        JOIN remote_training_catalog_sections AS cs
          ON cs.package_id = cp.id
         AND LOWER(TRIM(cs.title)) = LOWER(TRIM(s.title))
        WHERE p.source_catalog_package_id IS NOT NULL
          AND (
              SELECT COUNT(*)
              FROM remote_training_catalog_sections AS cs2
              WHERE cs2.package_id = cp.id
                AND LOWER(TRIM(cs2.title)) = LOWER(TRIM(s.title))
          ) = 1
          AND (
              SELECT COUNT(*)
              FROM remote_training_sections AS s2
              WHERE s2.program_id = p.id
                AND LOWER(TRIM(s2.title)) = LOWER(TRIM(s.title))
          ) = 1
          AND NOT EXISTS (
              SELECT 1
              FROM remote_training_catalog_section_links AS l
              WHERE l.program_section_id = s.id
                 OR (l.program_id = p.id AND l.catalog_section_id = cs.id)
          )
    """))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "remote_training_catalog_section_links"):
        return
    op.drop_index(
        "ix_remote_catalog_section_links_source",
        table_name="remote_training_catalog_section_links",
    )
    op.drop_index(
        "ix_remote_catalog_section_links_package",
        table_name="remote_training_catalog_section_links",
    )
    op.drop_index(
        "ix_remote_catalog_section_links_program",
        table_name="remote_training_catalog_section_links",
    )
    op.drop_table("remote_training_catalog_section_links")
