from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.entities import HealthFitnessStatus, HealthRecordType


class HealthRecordCreate(BaseModel):
    company_id: int
    employee_id: int
    record_type: HealthRecordType
    examination_date: date
    next_examination_date: date | None = None
    fitness_status: HealthFitnessStatus = HealthFitnessStatus.PENDING
    physician_name: str | None = Field(default=None, max_length=160)
    summary: str | None = Field(default=None, max_length=2000)
    confidential_note: str | None = Field(default=None, max_length=3000)


class HealthRecordResponse(BaseModel):
    id: int
    company_id: int
    employee_id: int
    record_type: HealthRecordType
    examination_date: date
    next_examination_date: date | None
    fitness_status: HealthFitnessStatus
    physician_name: str | None
    summary: str | None
    created_by_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
