"""Dijital Personel Kartı için izole, şirket kapsamlı ve sürümlemeli modeller.

Bu modeller mevcut Employee, IsgProfessional ve User tablolarını değiştirmez.
Sağlık, adli sicil, maaş, disiplin, ev adresi veya başka restricted veri içermez.
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
    Text,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


PROFILE_SUBJECT_TYPES = ("employee", "professional")
PROFILE_STATUSES = ("active", "archived")
PROFILE_CONTACT_TYPES = (
    "corporate_email",
    "alternative_email",
    "business_phone",
    "mobile_phone",
)
PROFILE_VISIBILITIES = ("internal_only", "cv_eligible", "share_eligible")
PROFILE_VERIFICATION_STATUSES = ("unverified", "verified", "rejected")
PROFILE_ENTRY_STATUSES = ("active", "archived")
PROFILE_COMPETENCY_CATEGORIES = (
    "professional_duty",
    "certificate_based",
    "technical_specialization",
    "training_authority",
    "other",
)
PROFILE_EXPERIENCE_VISIBILITIES = ("internal_only", "cv_eligible")


class PersonnelProfile(Base):
    """Mevcut bir Employee veya IsgProfessional için şirket kapsamlı profil kökü."""

    __tablename__ = "personnel_profiles"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "employee_id", name="uq_personnel_profile_company_employee"
        ),
        UniqueConstraint(
            "company_id",
            "professional_id",
            name="uq_personnel_profile_company_professional",
        ),
        CheckConstraint(
            "(subject_type = 'employee' AND employee_id IS NOT NULL AND professional_id IS NULL) "
            "OR (subject_type = 'professional' AND professional_id IS NOT NULL AND employee_id IS NULL)",
            name="ck_personnel_profile_exact_subject",
        ),
        CheckConstraint(
            "subject_type IN ('employee','professional')",
            name="ck_personnel_profile_subject_type",
        ),
        CheckConstraint(
            "status IN ('active','archived')",
            name="ck_personnel_profile_status",
        ),
        Index("ix_personnel_profile_osgb", "osgb_id"),
        Index("ix_personnel_profile_company", "company_id"),
        Index("ix_personnel_profile_branch", "branch_id"),
        Index("ix_personnel_profile_employee", "employee_id"),
        Index("ix_personnel_profile_professional", "professional_id"),
        Index("ix_personnel_profile_user", "user_id"),
        Index("ix_personnel_profile_status", "status"),
        Index("ix_personnel_profile_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    # 0083 keeps the historical workplace link while moving professional
    # profile ownership to the OSGB.  The migration adds this column to
    # existing databases; declaring it here keeps fresh metadata/test schemas
    # and the runtime model in sync without changing employee profile scope.
    legacy_company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=True
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    subject_type: Mapped[str] = mapped_column(String(24), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=True
    )
    professional_id: Mapped[int | None] = mapped_column(
        ForeignKey("isg_professionals.id", ondelete="RESTRICT"), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    archived_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


IMMUTABLE_PROFILE_SUBJECT_FIELDS = frozenset(
    {
        "osgb_id",
        "company_id",
        "branch_id",
        "subject_type",
        "employee_id",
        "professional_id",
        "user_id",
        "created_by_id",
        "created_at",
    }
)


@event.listens_for(PersonnelProfile, "before_update")
def _protect_profile_subject(_mapper, _connection, target) -> None:
    state = inspect(target)
    changed = sorted(
        field
        for field in IMMUTABLE_PROFILE_SUBJECT_FIELDS
        if state.attrs[field].history.has_changes()
    )
    if changed:
        raise ValueError(
            "Personel profil öznesi ve tenant bağlantıları yerinde değiştirilemez: "
            + ", ".join(changed)
        )

    status_history = state.attrs.status.history
    previous = (
        str(status_history.deleted[0])
        if status_history.deleted
        else str(target.status or "")
    )
    current = str(target.status or "")
    if previous == "archived" and current != "archived":
        raise ValueError("Arşivlenmiş personel profili yeniden aktifleştirilemez.")
    if previous == "active" and current not in {"active", "archived"}:
        raise ValueError("Personel profili yalnız arşivlenebilir.")


class PersonnelProfileContact(Base):
    """İletişim değerinin değişmez bir sürümü; ev adresi/acil kişi kapsam dışıdır."""

    __tablename__ = "personnel_profile_contacts"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "entry_key", "version", name="uq_personnel_contact_version"
        ),
        CheckConstraint("version > 0", name="ck_personnel_contact_version_positive"),
        CheckConstraint(
            "contact_type IN ('corporate_email','alternative_email','business_phone','mobile_phone')",
            name="ck_personnel_contact_type",
        ),
        CheckConstraint(
            "visibility IN ('internal_only','cv_eligible','share_eligible')",
            name="ck_personnel_contact_visibility",
        ),
        CheckConstraint(
            "verification_status IN ('unverified','verified','rejected')",
            name="ck_personnel_contact_verification",
        ),
        CheckConstraint(
            "lifecycle_status IN ('active','archived')",
            name="ck_personnel_contact_lifecycle",
        ),
        Index("ix_personnel_contact_profile", "profile_id"),
        Index("ix_personnel_contact_company", "company_id"),
        Index("ix_personnel_contact_entry_key", "entry_key"),
        Index("ix_personnel_contact_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("personnel_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    entry_key: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("personnel_profile_contacts.id", ondelete="RESTRICT"), nullable=True
    )
    contact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_value: Mapped[str] = mapped_column(String(320), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visibility: Mapped[str] = mapped_column(
        String(24), nullable=False, default="internal_only"
    )
    verification_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unverified"
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="active"
    )
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class PersonnelProfileCompetency(Base):
    """Mesleki görev/yeterlilik/uzmanlığın değişmez bir sürümü."""

    __tablename__ = "personnel_profile_competencies"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "entry_key", "version", name="uq_personnel_competency_version"
        ),
        CheckConstraint("version > 0", name="ck_personnel_competency_version_positive"),
        CheckConstraint(
            "category IN ('professional_duty','certificate_based','technical_specialization','training_authority','other')",
            name="ck_personnel_competency_category",
        ),
        CheckConstraint(
            "verification_status IN ('unverified','verified','rejected')",
            name="ck_personnel_competency_verification",
        ),
        CheckConstraint(
            "lifecycle_status IN ('active','archived')",
            name="ck_personnel_competency_lifecycle",
        ),
        Index("ix_personnel_competency_profile", "profile_id"),
        Index("ix_personnel_competency_company", "company_id"),
        Index("ix_personnel_competency_entry_key", "entry_key"),
        Index("ix_personnel_competency_category", "category"),
        Index("ix_personnel_competency_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("personnel_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    entry_key: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("personnel_profile_competencies.id", ondelete="RESTRICT"),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    certificate_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    issuing_organization: Mapped[str | None] = mapped_column(String(220), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unverified"
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="active"
    )
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class PersonnelProfileExperience(Base):
    """Gizli müşteri dokümanı içermeyen profesyonel deneyim özetinin sürümü."""

    __tablename__ = "personnel_profile_experiences"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "entry_key", "version", name="uq_personnel_experience_version"
        ),
        CheckConstraint("version > 0", name="ck_personnel_experience_version_positive"),
        CheckConstraint(
            "visibility IN ('internal_only','cv_eligible')",
            name="ck_personnel_experience_visibility",
        ),
        CheckConstraint(
            "lifecycle_status IN ('active','archived')",
            name="ck_personnel_experience_lifecycle",
        ),
        Index("ix_personnel_experience_profile", "profile_id"),
        Index("ix_personnel_experience_company", "company_id"),
        Index("ix_personnel_experience_entry_key", "entry_key"),
        Index("ix_personnel_experience_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("personnel_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    entry_key: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("personnel_profile_experiences.id", ondelete="RESTRICT"),
        nullable=True,
    )
    organization_name: Mapped[str] = mapped_column(String(220), nullable=False)
    position: Mapped[str] = mapped_column(String(180), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(160), nullable=True)
    nace_activity: Mapped[str | None] = mapped_column(String(300), nullable=True)
    project_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    professional_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(
        String(24), nullable=False, default="internal_only"
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="active"
    )
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


IMMUTABLE_VERSIONED_MODEL_FIELDS = {
    PersonnelProfileContact: frozenset(column.name for column in PersonnelProfileContact.__table__.columns),
    PersonnelProfileCompetency: frozenset(column.name for column in PersonnelProfileCompetency.__table__.columns),
    PersonnelProfileExperience: frozenset(column.name for column in PersonnelProfileExperience.__table__.columns),
}


def _prevent_version_update(_mapper, _connection, target) -> None:
    state = inspect(target)
    protected = IMMUTABLE_VERSIONED_MODEL_FIELDS[type(target)]
    changed = sorted(
        field for field in protected if state.attrs[field].history.has_changes()
    )
    if changed:
        raise ValueError(
            "Personel profil sürüm kayıtları değiştirilemez; yeni sürüm oluşturun: "
            + ", ".join(changed)
        )


for _version_model in IMMUTABLE_VERSIONED_MODEL_FIELDS:
    event.listen(_version_model, "before_update", _prevent_version_update)
