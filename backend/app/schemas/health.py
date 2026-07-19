from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import HealthFitnessStatus, HealthRecordType


class HealthRecordCreate(BaseModel):
    company_id: int
    employee_id: int
    record_type: HealthRecordType = HealthRecordType.PERIODIC_EXAM
    examination_date: date
    next_examination_date: date | None = None
    fitness_status: HealthFitnessStatus = HealthFitnessStatus.PENDING
    physician_name: str | None = Field(default=None, max_length=160)
    summary: str | None = Field(default=None, max_length=2000)
    confidential_note: str | None = Field(default=None, max_length=3000)
    audiometry_date: date | None = None
    audiometry_result: str | None = Field(default=None, max_length=240)
    spirometry_date: date | None = None
    spirometry_result: str | None = Field(default=None, max_length=240)
    chest_xray_date: date | None = None
    chest_xray_result: str | None = Field(default=None, max_length=240)
    blood_lead_date: date | None = None
    blood_lead_value: float | None = None
    blood_lead_unit: str | None = Field(default="µg/dL", max_length=20)
    blood_lead_ref: float | None = None
    suggested_tests: str | None = Field(default=None, max_length=1000)
    exposures: str | None = Field(default=None, max_length=1000)
    follow_up_note: str | None = Field(default=None, max_length=1500)
    other_biological_test: str | None = Field(default=None, max_length=1000)


class HealthRecordUpdate(BaseModel):
    record_type: HealthRecordType | None = None
    examination_date: date | None = None
    next_examination_date: date | None = None
    fitness_status: HealthFitnessStatus | None = None
    physician_name: str | None = Field(default=None, max_length=160)
    summary: str | None = Field(default=None, max_length=2000)
    confidential_note: str | None = Field(default=None, max_length=3000)
    audiometry_date: date | None = None
    audiometry_result: str | None = Field(default=None, max_length=240)
    spirometry_date: date | None = None
    spirometry_result: str | None = Field(default=None, max_length=240)
    chest_xray_date: date | None = None
    chest_xray_result: str | None = Field(default=None, max_length=240)
    blood_lead_date: date | None = None
    blood_lead_value: float | None = None
    blood_lead_unit: str | None = Field(default=None, max_length=20)
    blood_lead_ref: float | None = None
    suggested_tests: str | None = Field(default=None, max_length=1000)
    exposures: str | None = Field(default=None, max_length=1000)
    follow_up_note: str | None = Field(default=None, max_length=1500)
    other_biological_test: str | None = Field(default=None, max_length=1000)


class HealthRecordResponse(BaseModel):
    id: int
    company_id: int
    employee_id: int
    employee_name: str | None = None
    job_title: str | None = None
    department: str | None = None
    record_type: HealthRecordType
    examination_date: date
    next_examination_date: date | None
    fitness_status: HealthFitnessStatus
    physician_name: str | None
    summary: str | None
    confidential_note: str | None = None
    audiometry_date: date | None = None
    audiometry_result: str | None = None
    spirometry_date: date | None = None
    spirometry_result: str | None = None
    chest_xray_date: date | None = None
    chest_xray_result: str | None = None
    blood_lead_date: date | None = None
    blood_lead_value: float | None = None
    blood_lead_unit: str | None = None
    blood_lead_ref: float | None = None
    blood_lead_eval: str | None = None
    suggested_tests: str | None = None
    exposures: str | None = None
    follow_up_note: str | None = None
    other_biological_test: str | None = None
    report_file_name: str | None = None
    has_report: bool = False
    smart_summary: str | None = None
    tetkik_summary: str | None = None
    is_overdue: bool = False
    created_by_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
