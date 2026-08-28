"""Stable source links for materialized remote-training curriculum rows.

The original catalog materialization intentionally copied sections into company
snapshots.  Copies preserve audit history, but order_index is mutable in the
catalog and therefore cannot be used as a permanent identity.  This additive
link table gives live catalog synchronization a stable identity without
rewriting or deleting any historical training row.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RemoteTrainingCatalogSectionLink(Base):
    __tablename__ = "remote_training_catalog_section_links"
    __table_args__ = (
        UniqueConstraint(
            "program_id",
            "catalog_section_id",
            name="uq_remote_catalog_section_link_program_source",
        ),
        UniqueConstraint(
            "program_section_id",
            name="uq_remote_catalog_section_link_program_section",
        ),
        Index("ix_remote_catalog_section_links_program", "program_id"),
        Index("ix_remote_catalog_section_links_package", "catalog_package_id"),
        Index("ix_remote_catalog_section_links_source", "catalog_section_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    program_section_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    catalog_package_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_catalog_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    catalog_section_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_catalog_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
