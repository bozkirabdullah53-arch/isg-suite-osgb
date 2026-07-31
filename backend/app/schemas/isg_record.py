from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.entities import IsgModule, RecordStatus


class IsgRecordCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    module: IsgModule
    title: str = Field(min_length=3, max_length=220)
    description: str | None = Field(default=None, max_length=2000)
    status: RecordStatus = RecordStatus.OPEN
    severity: str | None = None
    event_date: date | None = None
    due_date: date | None = None
    responsible_name: str | None = None
    probability: int | None = Field(default=None, ge=1, le=5)
    impact: int | None = Field(default=None, ge=1, le=5)
    participant_count: int | None = Field(default=None, ge=0)


class IsgRecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=220)
    description: str | None = Field(default=None, max_length=2000)
    status: RecordStatus | None = None
    severity: str | None = None
    due_date: date | None = None
    responsible_name: str | None = None


class IsgRecordResponse(BaseModel):
    id: int
    company_id: int
    branch_id: int | None
    module: IsgModule
    title: str
    description: str | None
    status: RecordStatus
    severity: str | None
    event_date: date | None
    due_date: date | None
    responsible_name: str | None
    probability: int | None
    impact: int | None
    risk_score: int | None
    participant_count: int | None
    created_by_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
