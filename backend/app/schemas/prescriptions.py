from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.entities import PrescriptionStatus


class PrescriptionItemInput(BaseModel):
    medication_name: str = Field(min_length=2, max_length=240)
    medication_code: str | None = Field(default=None, max_length=80)
    dose: str = Field(min_length=1, max_length=120)
    frequency: str = Field(min_length=1, max_length=120)
    route: str | None = Field(default=None, max_length=80)
    duration: str | None = Field(default=None, max_length=120)
    quantity: int = Field(default=1, ge=1, le=99)
    usage_instruction: str | None = Field(default=None, max_length=1000)
    sort_order: int = Field(default=0, ge=0)


class PrescriptionCreate(BaseModel):
    company_id: int
    employee_id: int
    health_record_id: int | None = None
    prescription_date: date
    diagnosis_code: str | None = Field(default=None, max_length=32)
    diagnosis_text: str | None = Field(default=None, max_length=1000)
    clinical_note: str | None = Field(default=None, max_length=2000)
    items: list[PrescriptionItemInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_content(self):
        if not (self.diagnosis_code or (self.diagnosis_text or "").strip()):
            raise ValueError("Tanı kodu veya tanı açıklaması zorunludur.")
        return self


class PrescriptionUpdate(BaseModel):
    prescription_date: date | None = None
    diagnosis_code: str | None = Field(default=None, max_length=32)
    diagnosis_text: str | None = Field(default=None, max_length=1000)
    clinical_note: str | None = Field(default=None, max_length=2000)
    items: list[PrescriptionItemInput] | None = Field(default=None, min_length=1, max_length=20)


class PrescriptionItemResponse(PrescriptionItemInput):
    id: int
    model_config = ConfigDict(from_attributes=True)


class PrescriptionResponse(BaseModel):
    id: int
    company_id: int
    employee_id: int
    health_record_id: int | None
    physician_user_id: int
    physician_name: str | None = None
    employee_name: str | None = None
    company_name: str | None = None
    status: PrescriptionStatus
    prescription_date: date
    diagnosis_code: str | None
    diagnosis_text: str | None
    clinical_note: str | None
    medula_prescription_no: str | None
    approved_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    version: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    items: list[PrescriptionItemResponse] = []
    medula_configured: bool = False
    model_config = ConfigDict(from_attributes=True)


class PrescriptionCancel(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)
