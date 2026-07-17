from datetime import date
from pydantic import BaseModel, ConfigDict, Field
class EmployeeCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    full_name: str = Field(min_length=2, max_length=160)
    national_id_masked: str | None = None
    job_title: str | None = None
    department: str | None = None
    start_date: date | None = None
    special_status: str | None = None
class EmployeeUpdate(BaseModel):
    branch_id: int | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    national_id_masked: str | None = None
    job_title: str | None = None
    department: str | None = None
    start_date: date | None = None
    special_status: str | None = None
    is_active: bool | None = None
class EmployeeResponse(EmployeeCreate):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
