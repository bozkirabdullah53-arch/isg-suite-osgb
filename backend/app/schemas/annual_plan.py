from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.input_rules import assert_date_order, assert_event_date, assert_meaningful_text, assert_person_name
from app.models.entities import AnnualPlanStatus


class AnnualPlanCreate(BaseModel):
    company_id: int
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    category: str = Field(default="yillik_calisma", max_length=40)
    activity: str = Field(min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=2000)
    responsible_name: str | None = Field(default=None, max_length=160)
    target_date: date | None = None
    status: AnnualPlanStatus = AnnualPlanStatus.PLANNED
    completion_date: date | None = None
    notes: str | None = Field(default=None, max_length=1500)

    @model_validator(mode="after")
    def sanitize(self):
        self.activity = assert_meaningful_text(self.activity, label="Faaliyet", min_len=3, required=True)
        self.description = assert_meaningful_text(self.description, label="Açıklama", min_len=3, required=False)
        self.notes = assert_meaningful_text(self.notes, label="Notlar", min_len=3, required=False)
        self.responsible_name = assert_person_name(self.responsible_name, label="Sorumlu")
        self.target_date = assert_event_date(
            self.target_date, label="Hedef tarih", required=False, allow_future_days=800
        )
        self.completion_date = assert_event_date(
            self.completion_date, label="Tamamlanma tarihi", required=False, allow_future_days=0
        )
        assert_date_order(
            self.target_date,
            self.completion_date,
            earlier_label="Hedef tarih",
            later_label="Tamamlanma tarihi",
        )
        return self


class AnnualPlanUpdate(BaseModel):
    year: int | None = Field(default=None, ge=2020, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    category: str | None = Field(default=None, max_length=40)
    activity: str | None = Field(default=None, min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=2000)
    responsible_name: str | None = Field(default=None, max_length=160)
    target_date: date | None = None
    status: AnnualPlanStatus | None = None
    completion_date: date | None = None
    notes: str | None = Field(default=None, max_length=1500)

    @model_validator(mode="after")
    def sanitize(self):
        if self.activity is not None:
            self.activity = assert_meaningful_text(self.activity, label="Faaliyet", min_len=3, required=True)
        if self.description is not None:
            self.description = assert_meaningful_text(self.description, label="Açıklama", min_len=3, required=False)
        if self.notes is not None:
            self.notes = assert_meaningful_text(self.notes, label="Notlar", min_len=3, required=False)
        if self.responsible_name is not None:
            self.responsible_name = assert_person_name(self.responsible_name, label="Sorumlu")
        if self.target_date is not None:
            self.target_date = assert_event_date(
                self.target_date, label="Hedef tarih", required=False, allow_future_days=800
            )
        if self.completion_date is not None:
            self.completion_date = assert_event_date(
                self.completion_date, label="Tamamlanma tarihi", required=False, allow_future_days=0
            )
        assert_date_order(
            self.target_date,
            self.completion_date,
            earlier_label="Hedef tarih",
            later_label="Tamamlanma tarihi",
        )
        return self


class AnnualPlanResponse(BaseModel):
    id: int
    company_id: int
    year: int
    month: int
    category: str | None = None
    activity: str
    description: str | None = None
    responsible_name: str | None = None
    target_date: date | None = None
    status: AnnualPlanStatus
    completion_date: date | None = None
    notes: str | None = None
    created_by_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AnnualPlanGenerate(BaseModel):
    company_id: int
    year: int = Field(ge=2020, le=2100)
