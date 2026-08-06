"""Dijital Personel Kartı için private, append-only belge sürümleri.

Bu model yalnız sıradan profesyonel profil belgelerini kapsar. Sağlık, adli sicil,
biyometrik veri ve diğer restricted içerikler bu tabloda işlenmez.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


PROFILE_DOCUMENT_KINDS = (
    "profile_photo",
    "cv",
    "qualification",
    "certificate",
)
PROFILE_DOCUMENT_CATEGORIES = (
    "profile_photo",
    "cv",
    "diploma",
    "graduation_certificate",
    "occupational_safety_certificate",
    "workplace_physician_certificate",
    "other_health_personnel_certificate",
    "trainer_certificate",
    "myk_certificate",
    "mastership_certificate",
    "journeyman_certificate",
    "operator_certificate",
    "first_aid_certificate",
    "working_at_height_certificate",
    "fire_safety_certificate",
    "emergency_response_certificate",
    "explosion_protection_certificate",
    "risk_assessment_certificate",
    "electrical_work_certificate",
    "scaffolding_certificate",
    "welding_certificate",
    "hygiene_certificate",
    "language_certificate",
    "other_professional_document",
)
PROFILE_DOCUMENT_ACCESS = ("internal_only", "cv_eligible", "share_eligible")
PROFILE_DOCUMENT_VERIFICATION = ("unverified", "verified", "rejected")
PROFILE_DOCUMENT_LIFECYCLE = ("active", "archived")


class PersonnelProfileDocument(Base):
    """Sıradan profil belgesinin değişmez bir sürümü."""

    __tablename__ = "personnel_profile_documents"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "document_key",
            "version",
            name="uq_personnel_profile_document_version",
        ),
        UniqueConstraint(
            "profile_id",
            "idempotency_key",
            name="uq_personnel_profile_document_idempotency",
        ),
        CheckConstraint(
            "version > 0",
            name="ck_personnel_profile_document_version_positive",
        ),
        CheckConstraint(
            "document_kind IN ('profile_photo','cv','qualification','certificate')",
            name="ck_personnel_profile_document_kind",
        ),
        CheckConstraint(
            "category IN ("
            "'profile_photo','cv','diploma','graduation_certificate',"
            "'occupational_safety_certificate','workplace_physician_certificate',"
            "'other_health_personnel_certificate','trainer_certificate',"
            "'myk_certificate','mastership_certificate','journeyman_certificate',"
            "'operator_certificate','first_aid_certificate',"
            "'working_at_height_certificate','fire_safety_certificate',"
            "'emergency_response_certificate','explosion_protection_certificate',"
            "'risk_assessment_certificate','electrical_work_certificate',"
            "'scaffolding_certificate','welding_certificate','hygiene_certificate',"
            "'language_certificate','other_professional_document'"
            ")",
            name="ck_personnel_profile_document_category",
        ),
        CheckConstraint(
            "access_classification IN ('internal_only','cv_eligible','share_eligible')",
            name="ck_personnel_profile_document_access",
        ),
        CheckConstraint(
            "verification_status IN ('unverified','verified','rejected')",
            name="ck_personnel_profile_document_verification",
        ),
        CheckConstraint(
            "lifecycle_status IN ('active','archived')",
            name="ck_personnel_profile_document_lifecycle",
        ),
        Index("ix_personnel_profile_document_profile", "profile_id"),
        Index("ix_personnel_profile_document_company", "company_id"),
        Index("ix_personnel_profile_document_key", "document_key"),
        Index("ix_personnel_profile_document_kind", "document_kind"),
        Index("ix_personnel_profile_document_category", "category"),
        Index("ix_personnel_profile_document_expiration", "expiration_date"),
        Index("ix_personnel_profile_document_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("personnel_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_key: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("personnel_profile_documents.id", ondelete="RESTRICT"),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    document_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    issuing_organization: Mapped[str | None] = mapped_column(String(220), nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    no_expiration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    access_classification: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="internal_only",
    )
    processing_purpose: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="professional_profile_management",
    )
    retention_policy: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="personnel_profile_ordinary_v1",
    )
    verification_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="unverified",
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="active",
    )
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )


_DOCUMENT_IMMUTABLE_FIELDS = frozenset(
    column.name for column in PersonnelProfileDocument.__table__.columns
)


@event.listens_for(PersonnelProfileDocument, "before_update")
def _prevent_document_version_update(_mapper, _connection, target) -> None:
    state = inspect(target)
    changed = sorted(
        field
        for field in _DOCUMENT_IMMUTABLE_FIELDS
        if state.attrs[field].history.has_changes()
    )
    if changed:
        raise ValueError(
            "Personel profil belge sürümleri değiştirilemez; yeni sürüm oluşturun: "
            + ", ".join(changed)
        )
