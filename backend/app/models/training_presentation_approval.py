"""Immutable approval audit records for NACE training presentation versions."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrainingPresentationApproval(Base):
    """One immutable approval event tied to exact manifest and output hashes."""

    __tablename__ = "training_presentation_approvals"
    __table_args__ = (
        UniqueConstraint(
            "presentation_version_id",
            name="uq_training_presentation_approval_version",
        ),
        UniqueConstraint("event_hash", name="uq_training_presentation_approval_event_hash"),
        CheckConstraint(
            "approval_method IN ('application_approval','qualified_esign')",
            name="ck_training_presentation_approval_method",
        ),
        Index("ix_training_presentation_approval_training", "training_id"),
        Index("ix_training_presentation_approval_company", "company_id"),
        Index("ix_training_presentation_approval_version", "presentation_version_id"),
        Index("ix_training_presentation_approval_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    presentation_version_id: Mapped[int] = mapped_column(
        ForeignKey("training_presentation_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    training_id: Mapped[int] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )

    approval_method: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    pptx_file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    pdf_file_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    approver_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approver_name: Mapped[str] = mapped_column(String(180), nullable=False)
    approver_role: Mapped[str] = mapped_column(String(80), nullable=False)
    approval_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    esign_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("e_signature_requests.id", ondelete="SET NULL"), nullable=True
    )
    esign_document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    esign_signed_document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    esign_verification_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    esign_certificate_serial: Mapped[str | None] = mapped_column(String(160), nullable=True)
    esign_evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    legal_notice: Mapped[str] = mapped_column(String(700), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


@event.listens_for(TrainingPresentationApproval, "before_update")
def _approval_update_forbidden(_mapper, _connection, _target) -> None:
    raise ValueError("Sunum onay kaydı değiştirilemez; yeni sunum sürümü oluşturun.")


@event.listens_for(TrainingPresentationApproval, "before_delete")
def _approval_delete_forbidden(_mapper, _connection, _target) -> None:
    raise ValueError("Sunum onay kaydı silinemez; tarihsel denetim izi korunmalıdır.")
