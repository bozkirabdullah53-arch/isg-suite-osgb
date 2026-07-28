"""6331 uyum sicilleri — Pydantic şemaları."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PeriodicControlCreate(BaseModel):
    company_id: int
    category: str = Field(min_length=2, max_length=40)
    equipment_name: str = Field(min_length=2, max_length=220)
    location: str | None = Field(default=None, max_length=220)
    serial_no: str | None = Field(default=None, max_length=120)
    last_control_date: date | None = None
    next_due_date: date | None = None
    control_firm: str | None = Field(default=None, max_length=220)
    report_ref: str | None = Field(default=None, max_length=220)
    result: str | None = Field(default=None, max_length=40)
    document_id: int | None = None
    notes: str | None = Field(default=None, max_length=2000)


class PeriodicControlUpdate(BaseModel):
    category: str | None = Field(default=None, max_length=40)
    equipment_name: str | None = Field(default=None, max_length=220)
    location: str | None = None
    serial_no: str | None = None
    last_control_date: date | None = None
    next_due_date: date | None = None
    control_firm: str | None = None
    report_ref: str | None = None
    result: str | None = None
    document_id: int | None = None
    notes: str | None = None
    is_active: bool | None = None


class PeriodicControlResponse(PeriodicControlCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    review_status: str = "unset"


class EmergencyPlanCreate(BaseModel):
    company_id: int
    title: str = Field(min_length=2, max_length=220)
    revision_no: str = Field(default="00", max_length=30)
    plan_date: date | None = None
    next_review_date: date | None = None
    assembly_areas: str | None = Field(default=None, max_length=1000)
    scenario_summary: str | None = Field(default=None, max_length=4000)
    kroki_file_name: str | None = None
    document_id: int | None = None
    status: str = Field(default="Aktif", max_length=40)
    notes: str | None = None


class EmergencyPlanUpdate(BaseModel):
    title: str | None = None
    revision_no: str | None = None
    plan_date: date | None = None
    next_review_date: date | None = None
    assembly_areas: str | None = None
    scenario_summary: str | None = None
    kroki_file_name: str | None = None
    document_id: int | None = None
    status: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class EmergencyPlanResponse(EmergencyPlanCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kroki_storage_path: str | None = None
    is_active: bool
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    review_status: str = "unset"


class MeasurementCreate(BaseModel):
    company_id: int
    measurement_type: str = Field(min_length=2, max_length=40)
    location: str | None = None
    measured_at: date
    value: str | None = None
    unit: str | None = None
    limit_value: str | None = None
    lab_name: str | None = None
    report_ref: str | None = None
    next_due_date: date | None = None
    document_id: int | None = None
    notes: str | None = None


class MeasurementUpdate(BaseModel):
    measurement_type: str | None = None
    location: str | None = None
    measured_at: date | None = None
    value: str | None = None
    unit: str | None = None
    limit_value: str | None = None
    lab_name: str | None = None
    report_ref: str | None = None
    next_due_date: date | None = None
    document_id: int | None = None
    notes: str | None = None
    is_active: bool | None = None


class MeasurementResponse(MeasurementCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    review_status: str = "unset"


class CommitteeMemberCreate(BaseModel):
    company_id: int
    role_code: str = Field(min_length=2, max_length=40)
    full_name: str = Field(min_length=2, max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None


class CommitteeMemberResponse(CommitteeMemberCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_by_id: int
    created_at: datetime


class CommitteeMeetingCreate(BaseModel):
    company_id: int
    meeting_date: date
    agenda: str | None = None
    decisions: str | None = None
    attendees: str | None = None
    next_meeting_date: date | None = None
    document_id: int | None = None
    notes: str | None = None


class CommitteeMeetingResponse(CommitteeMeetingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_by_id: int
    created_at: datetime


class DocumentApprovalCreate(BaseModel):
    company_id: int
    document_title: str = Field(min_length=2, max_length=220)
    document_kind: str = Field(default="genel", max_length=80)
    approver_name: str = Field(min_length=2, max_length=160)
    approver_role: str | None = None
    approved_at: date | None = None
    signature_note: str | None = None
    status: str = Field(default="Bekliyor", max_length=40)
    document_id: int | None = None


class DocumentApprovalResponse(DocumentApprovalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_by_id: int
    created_at: datetime
