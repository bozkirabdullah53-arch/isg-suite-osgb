from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

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
