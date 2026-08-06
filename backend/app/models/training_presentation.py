"""Append-only NACE training presentation versions.

The table is isolated from the core training, exam, PDF and certificate models.
Every row freezes the presentation manifest and all source classifications used
for that version. Existing source snapshots are never rewritten; changed
content creates a new version. Only lifecycle/output fields may change later.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


PRESENTATION_VERSION_STATUSES = (
    "draft",
    "generated",
    "approved",
    "failed",
    "archived",
)

IMMUTABLE_PRESENTATION_SOURCE_FIELDS = frozenset(
    {
        "training_id",
        "company_id",
        "branch_id",
        "nace_snapshot_id",
        "version",
        "contract_version",
        "contract_hash",
        "template_version",
        "manifest_version",
        "manifest_json",
        "manifest_hash",
        "catalog_key",
        "nace_code",
        "nace_description",
        "hazard_class",
        "content_profile_code",
        "catalog_version",
        "catalog_hash",
        "source_snapshot_json",
        "training_topics_json",
        "technical_risk_tags_json",
        "special_risks_json",
        "output_formats_json",
        "primary_output_format",
        "created_by_id",
        "created_at",
    }
)


class TrainingPresentationVersion(Base):
    """One immutable source/manifest snapshot and its future rendered outputs."""

    __tablename__ = "training_presentation_versions"
    __table_args__ = (
        UniqueConstraint(
            "training_id",
            "version",
            name="uq_training_presentation_training_version",
        ),
        CheckConstraint("version > 0", name="ck_training_presentation_version_positive"),
        CheckConstraint(
            "status IN ('draft','generated','approved','failed','archived')",
            name="ck_training_presentation_status",
        ),
        Index("ix_training_presentation_training_id", "training_id"),
        Index("ix_training_presentation_company_id", "company_id"),
        Index("ix_training_presentation_branch_id", "branch_id"),
        Index("ix_training_presentation_status", "status"),
        Index("ix_training_presentation_manifest_hash", "manifest_hash"),
        Index("ix_training_presentation_catalog_hash", "catalog_hash"),
        Index("ix_training_presentation_created_at", "created_at"),
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
    nace_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_nace_snapshots.id", ondelete="SET NULL"), nullable=True
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")

    contract_version: Mapped[str] = mapped_column(String(120), nullable=False)
    contract_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    template_version: Mapped[str] = mapped_column(String(120), nullable=False)
    manifest_version: Mapped[str] = mapped_column(String(120), nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    catalog_key: Mapped[str] = mapped_column(String(140), nullable=False)
    nace_code: Mapped[str] = mapped_column(String(20), nullable=False)
    nace_description: Mapped[str] = mapped_column(String(500), nullable=False)
    hazard_class: Mapped[str] = mapped_column(String(40), nullable=False)
    content_profile_code: Mapped[str] = mapped_column(String(140), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(80), nullable=False)
    catalog_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    training_topics_json: Mapped[str] = mapped_column(Text, nullable=False)
    technical_risk_tags_json: Mapped[str] = mapped_column(Text, nullable=False)
    special_risks_json: Mapped[str] = mapped_column(Text, nullable=False)

    output_formats_json: Mapped[str] = mapped_column(Text, nullable=False, default='["pptx","pdf"]')
    primary_output_format: Mapped[str] = mapped_column(String(16), nullable=False, default="pptx")
    pptx_storage_key: Mapped[str | None] = mapped_column(String(700), nullable=True)
    pptx_file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pptx_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pptx_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pdf_storage_key: Mapped[str | None] = mapped_column(String(700), nullable=True)
    pdf_file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pdf_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pdf_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


@event.listens_for(TrainingPresentationVersion, "before_update")
def _protect_presentation_source_snapshot(_mapper, _connection, target) -> None:
    """Reject in-place edits to frozen source/manifest fields."""
    state = inspect(target)
    changed = sorted(
        field
        for field in IMMUTABLE_PRESENTATION_SOURCE_FIELDS
        if state.attrs[field].history.has_changes()
    )
    if changed:
        raise ValueError(
            "Sunum kaynak snapshot alanları değiştirilemez; yeni sürüm oluşturun: "
            + ", ".join(changed)
        )
