"""Yetkili firma ve uygunluk yönetimi için eklemeli, tenant-kapsamlı modeller."""
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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuthorizedFirmProfile(Base):
    __tablename__ = "authorized_firm_profiles"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_authorized_firm_company"),
        CheckConstraint(
            "authorization_expiry_date IS NULL OR authorization_start_date IS NULL "
            "OR authorization_expiry_date >= authorization_start_date",
            name="ck_authorized_firm_authorization_period",
        ),
        CheckConstraint(
            "authorization_expiry_date IS NULL OR authorization_issue_date IS NULL "
            "OR authorization_expiry_date >= authorization_issue_date",
            name="ck_authorized_firm_issue_expiry",
        ),
        CheckConstraint(
            "review_state IN ('internal_record','manually_reviewed')",
            name="ck_authorized_firm_review_state",
        ),
        CheckConstraint(
            "onboarding_status IN ('draft','in_progress','completed')",
            name="ck_authorized_firm_onboarding_status",
        ),
        CheckConstraint(
            "onboarding_current_step >= 1 AND onboarding_current_step <= 11",
            name="ck_authorized_firm_onboarding_step",
        ),
        Index("ix_authorized_firm_osgb", "osgb_id"),
        Index("ix_authorized_firm_company", "company_id"),
        Index("ix_authorized_firm_location", "province", "district"),
        Index("ix_authorized_firm_expiry", "authorization_expiry_date"),
        Index("ix_authorized_firm_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    firm_name: Mapped[str] = mapped_column(String(220), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    firm_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    province: Mapped[str | None] = mapped_column(String(80), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authorized_representative: Mapped[str | None] = mapped_column(String(160), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    employee_count_declared: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hazard_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    authorization_scope: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    authorization_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    authorization_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    authorization_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    authorization_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    last_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="internal_record"
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    onboarding_current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    onboarding_completed_steps: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    onboarding_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="draft"
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AuthorizedFirmDocument(Base):
    __tablename__ = "authorized_firm_documents"
    __table_args__ = (
        CheckConstraint(
            "expiry_date IS NULL OR start_date IS NULL OR expiry_date >= start_date",
            name="ck_authorized_firm_document_period",
        ),
        CheckConstraint(
            "renewal_date IS NULL OR review_date IS NULL OR renewal_date >= review_date",
            name="ck_authorized_firm_document_review_period",
        ),
        Index("ix_authorized_firm_document_profile", "profile_id"),
        Index("ix_authorized_firm_document_company", "company_id"),
        Index("ix_authorized_firm_document_osgb", "osgb_id"),
        Index("ix_authorized_firm_document_expiry", "expiry_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("authorized_firm_profiles.id", ondelete="CASCADE"), nullable=False
    )
    osgb_id: Mapped[int] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    document_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_records.id", ondelete="SET NULL"), nullable=True
    )
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ProfessionalComplianceProfile(Base):
    __tablename__ = "professional_compliance_profiles"
    __table_args__ = (
        UniqueConstraint("professional_id", name="uq_professional_compliance_professional"),
        CheckConstraint(
            "certificate_expiry_date IS NULL OR certificate_issue_date IS NULL "
            "OR certificate_expiry_date >= certificate_issue_date",
            name="ck_professional_compliance_certificate_period",
        ),
        CheckConstraint(
            "document_renewal_date IS NULL OR document_review_date IS NULL "
            "OR document_renewal_date >= document_review_date",
            name="ck_professional_compliance_review_period",
        ),
        CheckConstraint(
            "required_documents_status IN ('complete','incomplete','review_required')",
            name="ck_professional_required_documents_status",
        ),
        Index("ix_professional_compliance_osgb", "osgb_id"),
        Index("ix_professional_compliance_expiry", "certificate_expiry_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="CASCADE"), nullable=False
    )
    professional_id: Mapped[int] = mapped_column(
        ForeignKey("isg_professionals.id", ondelete="CASCADE"), nullable=False
    )
    certificate_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    certificate_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    required_documents_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="review_required"
    )
    required_documents_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ComplianceScoreSnapshot(Base):
    __tablename__ = "compliance_score_snapshots"
    __table_args__ = (
        CheckConstraint(
            "overall_score >= 0 AND overall_score <= 100",
            name="ck_compliance_snapshot_overall_score",
        ),
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 100",
            name="ck_compliance_snapshot_quality_score",
        ),
        Index("ix_compliance_snapshot_profile", "profile_id", "created_at"),
        Index("ix_compliance_snapshot_company", "company_id"),
        Index("ix_compliance_snapshot_osgb", "osgb_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("authorized_firm_profiles.id", ondelete="CASCADE"), nullable=False
    )
    osgb_id: Mapped[int] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    category_scores_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    quality_scores_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    blockers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
