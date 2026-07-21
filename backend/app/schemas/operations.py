from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.input_rules import (
    assert_date_order,
    assert_event_date,
    assert_meaningful_text,
    assert_person_name,
    clean_text,
)
from app.models.entities import VisitStatus


class VisitCreate(BaseModel):
    osgb_id: int
    company_id: int
    professional_id: int | None = None
    visit_date: date
    start_time: str | None = None
    end_time: str | None = None
    duration_minutes: int = Field(default=0, ge=0, le=24 * 60)
    subject: str = Field(min_length=2, max_length=220)
    notes: str | None = None
    status: VisitStatus | None = None

    @model_validator(mode="after")
    def sanitize(self):
        self.visit_date = assert_event_date(self.visit_date, label="Ziyaret tarihi", allow_future_days=365)
        self.subject = assert_meaningful_text(self.subject, label="Ziyaret konusu", min_len=3, required=True)
        self.notes = assert_meaningful_text(self.notes, label="Notlar", min_len=3, required=False)
        self.start_time = clean_text(self.start_time)
        self.end_time = clean_text(self.end_time)
        return self


class VisitPlanCreate(BaseModel):
    """OSGB yöneticisi planlı ziyaret — defter zorunlu değil."""
    osgb_id: int
    company_id: int
    professional_id: int
    visit_date: date
    start_time: str | None = "09:00"
    end_time: str | None = "10:00"
    duration_minutes: int = Field(default=60, ge=0, le=24 * 60)
    subject: str = Field(default="Planlı saha ziyareti", min_length=2, max_length=220)
    notes: str | None = None

    @model_validator(mode="after")
    def sanitize(self):
        self.visit_date = assert_event_date(self.visit_date, label="Ziyaret tarihi", allow_future_days=365)
        self.subject = assert_meaningful_text(self.subject, label="Ziyaret konusu", min_len=3, required=True)
        self.notes = assert_meaningful_text(self.notes, label="Notlar", min_len=3, required=False)
        return self


class VisitGpsStamp(BaseModel):
    """Saha tamamlamada GPS + QR + imza."""
    gps_lat: float | None = Field(default=None, ge=-90, le=90)
    gps_lng: float | None = Field(default=None, ge=-180, le=180)
    gps_accuracy_m: float | None = Field(default=None, ge=0, le=50000)
    site_verify_code: str | None = Field(default=None, max_length=120)
    signature_data_url: str | None = Field(default=None, max_length=400_000)


class VisitUpdate(BaseModel):
    company_id: int | None = None
    visit_date: date | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    subject: str | None = Field(default=None, min_length=2, max_length=220)
    notes: str | None = None
    status: VisitStatus | None = None

    @model_validator(mode="after")
    def sanitize(self):
        if self.visit_date is not None:
            self.visit_date = assert_event_date(self.visit_date, label="Ziyaret tarihi", allow_future_days=365)
        if self.subject is not None:
            self.subject = assert_meaningful_text(self.subject, label="Ziyaret konusu", min_len=3, required=True)
        if self.notes is not None:
            self.notes = assert_meaningful_text(self.notes, label="Notlar", min_len=3, required=False)
        if self.start_time is not None:
            self.start_time = clean_text(self.start_time)
        if self.end_time is not None:
            self.end_time = clean_text(self.end_time)
        return self


class VisitResponse(BaseModel):
    id: int
    osgb_id: int
    company_id: int
    professional_id: int
    visit_date: date
    start_time: str | None = None
    end_time: str | None = None
    duration_minutes: int = 0
    subject: str
    notes: str | None = None
    notebook_file_name: str | None = None
    notebook_content_type: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    gps_accuracy_m: float | None = None
    gps_captured_at: datetime | None = None
    site_verified_at: datetime | None = None
    signature_file_name: str | None = None
    signature_captured_at: datetime | None = None
    status: VisitStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LeadCreate(BaseModel):
    osgb_id: int
    company_name: str = Field(min_length=2, max_length=220)
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    employee_count: int = Field(default=0, ge=0)
    hazard_class: str | None = None
    stage: str = "new"
    estimated_monthly_value: int = Field(default=0, ge=0)
    next_action_date: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def sanitize(self):
        self.company_name = assert_meaningful_text(self.company_name, label="Firma adı", min_len=2, required=True)
        self.contact_name = assert_person_name(self.contact_name, label="Yetkili")
        self.notes = assert_meaningful_text(self.notes, label="Notlar", min_len=3, required=False)
        self.next_action_date = assert_event_date(
            self.next_action_date, label="Sonraki işlem tarihi", required=False, allow_future_days=730
        )
        self.phone = clean_text(self.phone)
        self.email = clean_text(self.email)
        return self


class LeadResponse(LeadCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FinanceCreate(BaseModel):
    osgb_id: int
    company_id: int | None = None
    transaction_type: str
    category: str = "service"
    amount: int = Field(ge=0)
    transaction_date: date
    due_date: date | None = None
    status: str = "pending"
    description: str | None = None

    @model_validator(mode="after")
    def sanitize(self):
        self.transaction_date = assert_event_date(
            self.transaction_date, label="İşlem tarihi", allow_future_days=30
        )
        self.due_date = assert_event_date(
            self.due_date, label="Vade tarihi", required=False, allow_future_days=3650
        )
        assert_date_order(
            self.transaction_date,
            self.due_date,
            earlier_label="İşlem tarihi",
            later_label="Vade tarihi",
        )
        self.description = assert_meaningful_text(self.description, label="Açıklama", min_len=3, required=False)
        return self


class FinanceResponse(FinanceCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
