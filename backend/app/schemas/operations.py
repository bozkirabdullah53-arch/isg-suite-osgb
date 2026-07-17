from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.entities import VisitStatus

class VisitCreate(BaseModel):
    osgb_id: int
    company_id: int
    professional_id: int
    visit_date: date
    start_time: str | None = None
    end_time: str | None = None
    duration_minutes: int = Field(default=0, ge=0)
    subject: str = Field(min_length=2, max_length=220)
    notes: str | None = None

class VisitResponse(VisitCreate):
    id: int
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

class FinanceResponse(FinanceCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
