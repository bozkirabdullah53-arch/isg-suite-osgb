from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.entities import AnnualPlanStatus


class AnnualPlanCreate(BaseModel):
    company_id: int
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    activity: str = Field(min_length=3, max_length=240)
    responsible_name: str | None = Field(default=None, max_length=160)
    status: AnnualPlanStatus = AnnualPlanStatus.PLANNED
    completion_date: date | None = None
    notes: str | None = Field(default=None, max_length=1500)


class AnnualPlanResponse(AnnualPlanCreate):
    id: int
    created_by_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
