from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.input_rules import assert_date_order, assert_event_date, assert_meaningful_text, assert_person_name
from app.models.entities import HealthFitnessStatus, HealthRecordType


class HealthRecordCreate(BaseModel):
    company_id: int
    employee_id: int
    record_type: HealthRecordType = HealthRecordType.PERIODIC_EXAM
    examination_date: date
    next_examination_date: date | None = None
    fitness_status: HealthFitnessStatus = HealthFitnessStatus.PENDING
    physician_professional_id: int | None = None
    physician_name: str | None = Field(default=None, max_length=160)
    diagnosis: str | None = Field(default=None, max_length=3000)
    laboratory_result_summary: str | None = Field(default=None, max_length=3000)
    anamnesis_chronic_diseases: str | None = Field(default=None, max_length=3000)
    anamnesis_past_medical_history: str | None = Field(default=None, max_length=3000)
    anamnesis_family_history: str | None = Field(default=None, max_length=3000)
    anamnesis_current_medications: str | None = Field(default=None, max_length=2000)
    anamnesis_allergies: str | None = Field(default=None, max_length=2000)
    anamnesis_smoking_status: str | None = Field(default=None, max_length=40)
    anamnesis_smoking_pack_years: float | None = Field(default=None, ge=0, le=300)
    anamnesis_alcohol_use: str | None = Field(default=None, max_length=80)
    anamnesis_occupational_history: str | None = Field(default=None, max_length=5000)
    anamnesis_previous_exposures: str | None = Field(default=None, max_length=3000)
    anamnesis_current_complaints: str | None = Field(default=None, max_length=3000)
    summary: str | None = Field(default=None, max_length=2000)
    confidential_note: str | None = Field(default=None, max_length=3000)
    informed_consent: bool = False
    restrictions: str | None = Field(default=None, max_length=2000)
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

    @model_validator(mode="after")
    def sanitize(self):
        self.examination_date = assert_event_date(
            self.examination_date, label="Muayene tarihi", allow_future_days=0
        )
        self.next_examination_date = assert_event_date(
            self.next_examination_date, label="Sonraki muayene", required=False, allow_future_days=3650
        )
        assert_date_order(
            self.examination_date,
            self.next_examination_date,
            earlier_label="Muayene tarihi",
            later_label="Sonraki muayene",
        )
        self.physician_name = assert_person_name(self.physician_name, label="Hekim")
        self.summary = assert_meaningful_text(self.summary, label="Özet", min_len=5, required=False)
        self.restrictions = assert_meaningful_text(
            self.restrictions, label="Kısıtlamalar", min_len=3, required=False
        )
        self.follow_up_note = assert_meaningful_text(
            self.follow_up_note, label="Takip notu", min_len=3, required=False
        )
        return self


class HealthRecordUpdate(BaseModel):
    record_type: HealthRecordType | None = None
    examination_date: date | None = None
    next_examination_date: date | None = None
    fitness_status: HealthFitnessStatus | None = None
    physician_professional_id: int | None = None
    physician_name: str | None = Field(default=None, max_length=160)
    diagnosis: str | None = Field(default=None, max_length=3000)
    laboratory_result_summary: str | None = Field(default=None, max_length=3000)
    anamnesis_chronic_diseases: str | None = Field(default=None, max_length=3000)
    anamnesis_past_medical_history: str | None = Field(default=None, max_length=3000)
    anamnesis_family_history: str | None = Field(default=None, max_length=3000)
    anamnesis_current_medications: str | None = Field(default=None, max_length=2000)
    anamnesis_allergies: str | None = Field(default=None, max_length=2000)
    anamnesis_smoking_status: str | None = Field(default=None, max_length=40)
    anamnesis_smoking_pack_years: float | None = Field(default=None, ge=0, le=300)
    anamnesis_alcohol_use: str | None = Field(default=None, max_length=80)
    anamnesis_occupational_history: str | None = Field(default=None, max_length=5000)
    anamnesis_previous_exposures: str | None = Field(default=None, max_length=3000)
    anamnesis_current_complaints: str | None = Field(default=None, max_length=3000)
    summary: str | None = Field(default=None, max_length=2000)
    confidential_note: str | None = Field(default=None, max_length=3000)
    informed_consent: bool | None = None
    restrictions: str | None = Field(default=None, max_length=2000)
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

    @model_validator(mode="after")
    def sanitize_dates(self):
        if self.examination_date is not None:
            self.examination_date = assert_event_date(
                self.examination_date, label="Muayene tarihi", allow_future_days=0
            )
        if self.next_examination_date is not None:
            self.next_examination_date = assert_event_date(
                self.next_examination_date,
                label="Sonraki muayene",
                required=False,
                allow_future_days=3650,
            )
        if self.examination_date is not None and self.next_examination_date is not None:
            assert_date_order(
                self.examination_date,
                self.next_examination_date,
                earlier_label="Muayene tarihi",
                later_label="Sonraki muayene",
            )
        return self


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
    fitness_status: HealthFitnessStatus | None = None
    physician_professional_id: int | None = None
    physician_name: str | None
    diagnosis: str | None = None
    laboratory_result_summary: str | None = None
    anamnesis_chronic_diseases: str | None = None
    anamnesis_past_medical_history: str | None = None
    anamnesis_family_history: str | None = None
    anamnesis_current_medications: str | None = None
    anamnesis_allergies: str | None = None
    anamnesis_smoking_status: str | None = None
    anamnesis_smoking_pack_years: float | None = None
    anamnesis_alcohol_use: str | None = None
    anamnesis_occupational_history: str | None = None
    anamnesis_previous_exposures: str | None = None
    anamnesis_current_complaints: str | None = None
    summary: str | None
    confidential_note: str | None = None
    informed_consent: bool = False
    informed_consent_at: datetime | None = None
    restrictions: str | None = None
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
    blood_lead_limit: float | None = None
    blood_lead_medical_threshold: float | None = None
    blood_lead_status: str | None = None
    blood_lead_status_label: str | None = None
    blood_lead_exceeds_limit: bool = False
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
    updated_at: datetime
    version: int = 1
    model_config = ConfigDict(from_attributes=True)
