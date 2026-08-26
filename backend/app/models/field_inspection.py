"""GPS'li, fotoğraf kanıtlı görsel saha denetimi modelleri.

Bu dosya mevcut risk/ziyaret tablolarını değiştirmeden yeni görsel denetim
akışını izole eder. Onaylanmış bulguların mevcut risk ve DÖF kayıtlarına
bağlanabilmesi için nullable foreign key'ler kullanılır.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FieldHazardCategory(Base):
    __tablename__ = "field_hazard_categories"
    __table_args__ = (UniqueConstraint("name", name="uq_field_hazard_category_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    icon: Mapped[str | None] = mapped_column(String(60), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    hazards: Mapped[list["FieldHazard"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class FieldHazard(Base):
    __tablename__ = "field_hazards"
    __table_args__ = (
        UniqueConstraint(
            "category_id",
            "company_id",
            "osgb_id",
            "name",
            name="uq_field_hazard_category_company_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("field_hazard_categories.id", ondelete="CASCADE"), index=True
    )
    # NULL company_id means system/OSGB catalog; company-scoped custom hazards
    # never leak because the API always filters by the selected workplace.
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True
    )
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(220), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    equipment_scope: Mapped[str | None] = mapped_column(String(220), nullable=True)
    keywords_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    category: Mapped[FieldHazardCategory] = relationship(back_populates="hazards")


class FieldInspectionSite(Base):
    __tablename__ = "field_inspection_sites"
    __table_args__ = (
        UniqueConstraint("company_id", "name_key", name="uq_field_site_company_name_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    name_key: Mapped[str] = mapped_column(String(220), index=True)
    site_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    areas: Mapped[list["FieldInspectionArea"]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )


class FieldInspectionArea(Base):
    __tablename__ = "field_inspection_areas"
    __table_args__ = (
        UniqueConstraint("site_id", "name_key", name="uq_field_area_site_name_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspection_sites.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(220), index=True)
    name_key: Mapped[str] = mapped_column(String(220), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    site: Mapped[FieldInspectionSite] = relationship(back_populates="areas")


class FieldInspectionEquipment(Base):
    __tablename__ = "field_inspection_equipment"
    __table_args__ = (
        UniqueConstraint("area_id", "name_key", name="uq_field_equipment_area_name_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspection_sites.id", ondelete="CASCADE"), index=True
    )
    area_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspection_areas.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(220), index=True)
    name_key: Mapped[str] = mapped_column(String(220), index=True)
    equipment_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FieldInspection(Base):
    __tablename__ = "field_inspections"
    __table_args__ = (
        UniqueConstraint("company_id", "client_reference", name="uq_field_inspection_company_client_ref"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspection_sites.id", ondelete="RESTRICT"), index=True
    )
    area_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspection_areas.id", ondelete="RESTRICT"), index=True
    )
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("field_inspection_equipment.id", ondelete="SET NULL"), nullable=True, index=True
    )
    inspection_date: Mapped[date] = mapped_column(Date, index=True)
    inspection_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Istanbul")
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    gps_status: Mapped[str] = mapped_column(String(30), default="not_available", index=True)
    gps_provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    gps_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manual_location_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    selected_category_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_hazard_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    scan_all_hazards: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_reference: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    ai_status: Mapped[str] = mapped_column(String(40), default="not_started", index=True)
    ai_job_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ai_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ai_prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ai_analysis_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_general_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_revision_no: Mapped[int] = mapped_column(Integer, default=1)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    photos: Mapped[list["FieldInspectionPhoto"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )
    findings: Mapped[list["FieldInspectionFinding"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )
    actions: Mapped[list["FieldInspectionAction"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )


class FieldInspectionPhoto(Base):
    __tablename__ = "field_inspection_photos"
    __table_args__ = (
        UniqueConstraint("inspection_id", "client_reference", name="uq_field_photo_inspection_client_ref"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspections.id", ondelete="CASCADE"), index=True
    )
    # A single inspection may contain evidence from different areas or pieces
    # of equipment.  Defaults are copied from the inspection at upload time,
    # while these nullable links allow an expert to select a different context
    # for an individual photo without changing the inspection header.
    site_id: Mapped[int | None] = mapped_column(
        ForeignKey("field_inspection_sites.id", ondelete="SET NULL"), nullable=True, index=True
    )
    area_id: Mapped[int | None] = mapped_column(
        ForeignKey("field_inspection_areas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("field_inspection_equipment.id", ondelete="SET NULL"), nullable=True, index=True
    )
    original_storage_path: Mapped[str] = mapped_column(String(500))
    analysis_storage_path: Mapped[str] = mapped_column(String(500))
    marked_storage_path: Mapped[str] = mapped_column(String(500))
    preview_storage_path: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(120), default="image/jpeg")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edit_meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    gps_status: Mapped[str] = mapped_column(String(30), default="not_available", index=True)
    gps_provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    gps_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manual_location_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    blur_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    client_reference: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    inspection: Mapped[FieldInspection] = relationship(back_populates="photos")
    findings: Mapped[list["FieldInspectionFinding"]] = relationship(back_populates="photo")
    annotations: Mapped[list["FieldInspectionAnnotation"]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )


class FieldInspectionFinding(Base):
    __tablename__ = "field_inspection_findings"
    __table_args__ = (
        UniqueConstraint("inspection_id", "finding_no", name="uq_field_finding_inspection_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspections.id", ondelete="CASCADE"), index=True
    )
    photo_id: Mapped[int | None] = mapped_column(
        ForeignKey("field_inspection_photos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    field_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("field_hazard_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    field_hazard_id: Mapped[int | None] = mapped_column(
        ForeignKey("field_hazards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    finding_no: Mapped[int] = mapped_column(Integer)
    category_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    hazard_name: Mapped[str] = mapped_column(String(220))
    area_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    equipment_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    visual_evidence: Mapped[str] = mapped_column(Text)
    nonconformity_description: Mapped[str] = mapped_column(Text)
    possible_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    possible_harm: Mapped[str | None] = mapped_column(Text, nullable=True)
    possible_accident_or_disease: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_priority: Mapped[str] = mapped_column(String(30), default="medium")
    priority_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgent_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrective_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    preventive_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    engineering_control: Mapped[str | None] = mapped_column(Text, nullable=True)
    administrative_control: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_need: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_ppe: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_responsible_role: Mapped[str | None] = mapped_column(String(180), nullable=True)
    suggested_term_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="ai_draft", index=True)
    source: Mapped[str] = mapped_column(String(30), default="ai")
    ai_model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ai_prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_risk_id: Mapped[int | None] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    linked_dof_id: Mapped[int | None] = mapped_column(
        ForeignKey("risk_dofs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inspection: Mapped[FieldInspection] = relationship(back_populates="findings")
    photo: Mapped[FieldInspectionPhoto | None] = relationship(back_populates="findings")
    annotations: Mapped[list["FieldInspectionAnnotation"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    legal_references: Mapped[list["FieldInspectionLegalReference"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    actions: Mapped[list["FieldInspectionAction"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class FieldInspectionAnnotation(Base):
    __tablename__ = "field_inspection_annotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspections.id", ondelete="CASCADE"), index=True
    )
    photo_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspection_photos.id", ondelete="CASCADE"), index=True
    )
    finding_id: Mapped[int | None] = mapped_column(
        ForeignKey("field_inspection_findings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    shape_type: Mapped[str] = mapped_column(String(30), default="rectangle")
    x: Mapped[float] = mapped_column(Float, default=0)
    y: Mapped[float] = mapped_column(Float, default=0)
    width: Mapped[float] = mapped_column(Float, default=0)
    height: Mapped[float] = mapped_column(Float, default=0)
    points_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    label: Mapped[str | None] = mapped_column(String(220), nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="#dc2626")
    source: Mapped[str] = mapped_column(String(20), default="manual")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    photo: Mapped[FieldInspectionPhoto] = relationship(back_populates="annotations")
    finding: Mapped[FieldInspectionFinding | None] = relationship(back_populates="annotations")


class FieldInspectionLegalReference(Base):
    __tablename__ = "field_inspection_legal_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspection_findings.id", ondelete="CASCADE"), index=True
    )
    regulation_name: Mapped[str] = mapped_column(String(300))
    article: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paragraph: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    relation_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="needs_expert_review")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    finding: Mapped[FieldInspectionFinding] = relationship(back_populates="legal_references")


class FieldInspectionAction(Base):
    __tablename__ = "field_inspection_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("field_inspections.id", ondelete="CASCADE"), index=True
    )
    finding_id: Mapped[int | None] = mapped_column(
        ForeignKey("field_inspection_findings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    activity: Mapped[str] = mapped_column(Text)
    urgent_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    permanent_solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    preventive_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsible_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    responsible_person: Mapped[str | None] = mapped_column(String(180), nullable=True)
    responsible_role: Mapped[str | None] = mapped_column(String(180), nullable=True)
    term_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(30), default="medium", index=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    evidence_photo_id: Mapped[int | None] = mapped_column(
        ForeignKey("field_inspection_photos.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expert_control_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    expert_control_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inspection: Mapped[FieldInspection] = relationship(back_populates="actions")
    finding: Mapped[FieldInspectionFinding | None] = relationship(back_populates="actions")
