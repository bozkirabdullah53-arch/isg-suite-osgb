from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.input_rules import assert_event_date, assert_meaningful_text, assert_person_name


class EmployeeCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    full_name: str = Field(min_length=2, max_length=160)
    national_id_masked: str | None = None
    job_title: str | None = None
    department: str | None = None
    start_date: date | None = None
    special_status: str | None = None

    @model_validator(mode="after")
    def sanitize(self):
        self.full_name = assert_person_name(self.full_name, label="Ad soyad", required=True)
        self.job_title = assert_meaningful_text(self.job_title, label="Görev / unvan", min_len=2, required=False)
        self.department = assert_meaningful_text(self.department, label="Departman", min_len=2, required=False)
        self.start_date = assert_event_date(
            self.start_date, label="İşe giriş tarihi", required=False, allow_future_days=30
        )
        return self


class EmployeeUpdate(BaseModel):
    branch_id: int | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    national_id_masked: str | None = None
    job_title: str | None = None
    department: str | None = None
    start_date: date | None = None
    special_status: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def sanitize(self):
        if self.full_name is not None:
            self.full_name = assert_person_name(self.full_name, label="Ad soyad", required=True)
        if self.job_title is not None:
            self.job_title = assert_meaningful_text(self.job_title, label="Görev / unvan", min_len=2, required=False)
        if self.department is not None:
            self.department = assert_meaningful_text(self.department, label="Departman", min_len=2, required=False)
        if self.start_date is not None:
            self.start_date = assert_event_date(
                self.start_date, label="İşe giriş tarihi", required=False, allow_future_days=30
            )
        return self


class EmployeeResponse(EmployeeCreate):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
