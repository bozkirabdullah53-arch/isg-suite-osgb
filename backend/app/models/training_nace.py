"""Immutable NACE classification snapshots for training records."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrainingNaceSnapshot(Base):
    """Frozen NACE, hazard, topic and risk classification used by one training."""

    __tablename__ = "training_nace_snapshots"
    __table_args__ = (
        UniqueConstraint("training_id", name="uq_training_nace_snapshot_training"),
        Index("ix_training_nace_snapshots_training_id", "training_id"),
        Index("ix_training_nace_snapshots_company_id", "company_id"),
        Index("ix_training_nace_snapshots_branch_id", "branch_id"),
        Index("ix_training_nace_snapshots_catalog_key", "catalog_key"),
        Index("ix_training_nace_snapshots_nace_code", "nace_code"),
        Index("ix_training_nace_snapshots_section", "nace_section_code"),
        Index("ix_training_nace_snapshots_profile", "content_profile_code"),
        Index("ix_training_nace_snapshots_hazard", "hazard_class"),
        Index("ix_training_nace_snapshots_status", "classification_status"),
        Index("ix_training_nace_snapshots_hash", "catalog_hash"),
        Index("ix_training_nace_snapshots_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    training_id: Mapped[int] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )

    catalog_key: Mapped[str | None] = mapped_column(String(140), nullable=True)
    nace_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nace_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nace_section_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    nace_section_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    subsector_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activity_group_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    content_profile_code: Mapped[str | None] = mapped_column(String(140), nullable=True)
    content_profile_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    hazard_class: Mapped[str | None] = mapped_column(String(40), nullable=True)

    training_topics_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    technical_risk_tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    special_risks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    required_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)

    classification_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="legacy_unverified"
    )
    catalog_version: Mapped[str] = mapped_column(String(80), nullable=False)
    catalog_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
