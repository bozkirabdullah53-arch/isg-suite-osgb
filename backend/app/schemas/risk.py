from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RiskCalculateRequest(BaseModel):
    probability: int = Field(ge=1, le=5)
    severity: int = Field(ge=1, le=5)
    term_override_days: int | None = Field(default=None, ge=0, le=365)


class RiskCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    department_id: int | None = None
    department_name: str | None = Field(default=None, max_length=200)
    hazard_id: int
    activity: str = Field(min_length=2, max_length=500)
    risk_definition: str = Field(min_length=3, max_length=2000)
    affected_people: str | None = Field(default=None, max_length=500)
    affected_group: str | None = Field(default=None, max_length=100)
    existing_measures: str | None = Field(default=None, max_length=2000)
    additional_measures: str | None = Field(default=None, max_length=2000)
    probability: int = Field(ge=1, le=5)
    severity: int = Field(ge=1, le=5)
    term_override_days: int | None = Field(default=None, ge=0, le=365)
    status: str = Field(default="Açık", max_length=50)

    @model_validator(mode="after")
    def department_required(self):
        if not self.department_id and not (self.department_name or "").strip():
            raise ValueError("Bölüm seçiniz veya yeni bölüm adı giriniz.")
        return self


class RiskUpdate(BaseModel):
    branch_id: int | None = None
    department_id: int | None = None
    department_name: str | None = Field(default=None, max_length=200)
    hazard_id: int | None = None
    activity: str | None = Field(default=None, min_length=2, max_length=500)
    risk_definition: str | None = Field(default=None, min_length=3, max_length=2000)
    affected_people: str | None = Field(default=None, max_length=500)
    affected_group: str | None = Field(default=None, max_length=100)
    existing_measures: str | None = Field(default=None, max_length=2000)
    additional_measures: str | None = Field(default=None, max_length=2000)
    probability: int | None = Field(default=None, ge=1, le=5)
    severity: int | None = Field(default=None, ge=1, le=5)
    term_override_days: int | None = Field(default=None, ge=0, le=365)
    status: str | None = Field(default=None, max_length=50)


class RiskDofCreate(BaseModel):
    description: str = Field(min_length=3, max_length=2000)
    responsible_person: str | None = Field(default=None, max_length=150)
    responsible_department: str | None = Field(default=None, max_length=150)
    term_date: date | None = None
    cost_estimate: int | None = Field(default=None, ge=0)


class RiskDofComplete(BaseModel):
    completion_note: str | None = Field(default=None, max_length=2000)


class RiskDofUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=3, max_length=2000)
    responsible_person: str | None = Field(default=None, max_length=150)
    responsible_department: str | None = Field(default=None, max_length=150)
    term_date: date | None = None
    cost_estimate: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, max_length=50)
    completion_note: str | None = Field(default=None, max_length=2000)


class RiskDofResponse(BaseModel):
    id: int
    dof_code: str
    risk_id: int
    description: str
    responsible_person: str | None
    responsible_department: str | None
    term_date: date | None
    completion_date: date | None
    cost_estimate: int | None
    currency: str
    status: str
    completion_note: str | None
    is_completed: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RiskMediaResponse(BaseModel):
    id: int
    risk_id: int
    original_name: str | None
    content_type: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RiskResponse(BaseModel):
    id: int
    risk_code: str
    company_id: int
    branch_id: int | None
    department_id: int | None = None
    hazard_id: int
    hazard_code: str | None = None
    hazard_name: str | None = None
    category_name: str | None = None
    department_name: str | None
    activity: str
    risk_definition: str
    affected_people: str | None
    affected_group: str | None
    existing_measures: str | None
    additional_measures: str | None
    probability: int
    severity: int
    risk_score: int
    risk_level: str
    term_days: int | None
    term_date: date | None
    term_suggested: int | None
    term_overridden: bool
    status: str
    revision_no: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    dofs: list[RiskDofResponse] = []
    media: list[RiskMediaResponse] = []
    model_config = ConfigDict(from_attributes=True)


class HazardCategoryResponse(BaseModel):
    id: int
    name: str
    icon: str | None
    sort_order: int
    hazard_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class HazardResponse(BaseModel):
    id: int
    category_id: int
    code: str
    name: str
    description: str | None
    risk_source: str | None
    default_probability: int | None
    default_severity: int | None
    regulations: list[str] = []
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class DepartmentCreate(BaseModel):
    company_id: int
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=500)


class DepartmentResponse(BaseModel):
    id: int
    company_id: int
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    risk_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=500)


class RiskDofListItem(BaseModel):
    id: int
    dof_code: str
    risk_id: int
    risk_code: str | None = None
    description: str
    responsible_person: str | None
    responsible_department: str | None
    term_date: date | None
    status: str
    is_completed: bool
    is_overdue: bool = False
    cost_estimate: int | None = None
    currency: str | None = None
    model_config = ConfigDict(from_attributes=True)
