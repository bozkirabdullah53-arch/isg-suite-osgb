"""Immutable NACE classification snapshots for training records."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrainingNaceSnapshot(Base):
    """Frozen NACE, hazard, topic and risk classification used by one training."""

    __tablename__ = "training_nace_snapshots"
    __table_args__ = (
        UniqueConstraint("training_id", name="uq_training_nace_snapshot_training"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    training_id: Mapped[int] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )

    catalog_key: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    nace_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    nace_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nace_section_code: Mapped[str | None] = mapped_column(String(4), nullable=True, index=True)
    nace_section_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    subsector_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activity_group_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    content_profile_code: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    content_profile_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    hazard_class: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)

    training_topics_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    technical_risk_tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    special_risks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    required_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)

    classification_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="legacy_unverified", index=True
    )
    catalog_version: Mapped[str] = mapped_column(String(80), nullable=False)
    catalog_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
