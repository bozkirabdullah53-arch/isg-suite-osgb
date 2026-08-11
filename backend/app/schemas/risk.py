from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RiskCalculateRequest(BaseModel):
    method_code: str = Field(default="5x5_l", max_length=40)
    probability: float = Field(gt=0, le=100)
    frequency: float | None = Field(default=None, gt=0, le=10)
    severity: float = Field(gt=0, le=100)
    term_override_days: int | None = Field(default=None, ge=0, le=365)


class HazardHintRequest(BaseModel):
    """Tehlike önerisi — faaliyet + risk tanımı metni."""
    text: str = Field(default="", max_length=4000)
    activity: str | None = Field(default=None, max_length=500)
    risk_definition: str | None = Field(default=None, max_length=2000)


class RiskAssessmentInfoUpdate(BaseModel):
    """Risk değerlendirme belgesi künyesi — tarih + ekip + belge kontrolü."""

    company_id: int
    assessment_date: date | None = None
    employee_representative: str | None = Field(default=None, max_length=160)
    support_staff: str | None = Field(default=None, max_length=160)
    method: str | None = Field(default=None, max_length=40)
    document_no: str | None = Field(default=None, max_length=80)
    revision_no: str | None = Field(default=None, max_length=20)
    revision_reason: str | None = Field(default=None, max_length=500)
    scope_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def not_in_future(self):
        if self.assessment_date and self.assessment_date > date.today():
            raise ValueError("Risk değerlendirme tarihi bugünden ileri olamaz.")
        for field in (
            "employee_representative",
            "support_staff",
            "method",
            "document_no",
            "revision_no",
            "revision_reason",
            "scope_note",
        ):
            value = getattr(self, field)
            if value is not None:
                setattr(self, field, value.strip() or None)
        return self


class RiskCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    department_id: int | None = None
    department_name: str | None = Field(default=None, max_length=200)
    hazard_id: int
    method_code: str | None = Field(default=None, max_length=40)
    activity: str = Field(min_length=2, max_length=500)
    risk_definition: str = Field(min_length=3, max_length=2000)
    affected_people: str | None = Field(default=None, max_length=500)
    affected_group: str | None = Field(default=None, max_length=100)
    existing_measures: str | None = Field(default=None, max_length=2000)
    additional_measures: str | None = Field(default=None, max_length=2000)
    probability: float = Field(gt=0, le=100)
    frequency: float | None = Field(default=None, gt=0, le=10)
    severity: float = Field(gt=0, le=100)
    residual_probability: float | None = Field(default=None, gt=0, le=100)
    residual_frequency: float | None = Field(default=None, gt=0, le=10)
    residual_severity: float | None = Field(default=None, gt=0, le=100)
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
    method_code: str | None = Field(default=None, max_length=40)
    activity: str | None = Field(default=None, min_length=2, max_length=500)
    risk_definition: str | None = Field(default=None, min_length=3, max_length=2000)
    affected_people: str | None = Field(default=None, max_length=500)
    affected_group: str | None = Field(default=None, max_length=100)
    existing_measures: str | None = Field(default=None, max_length=2000)
    additional_measures: str | None = Field(default=None, max_length=2000)
    probability: float | None = Field(default=None, gt=0, le=100)
    frequency: float | None = Field(default=None, gt=0, le=10)
    severity: float | None = Field(default=None, gt=0, le=100)
    residual_probability: float | None = Field(default=None, gt=0, le=100)
    residual_frequency: float | None = Field(default=None, gt=0, le=10)
    residual_severity: float | None = Field(default=None, gt=0, le=100)
    term_override_days: int | None = Field(default=None, ge=0, le=365)
    status: str | None = Field(default=None, max_length=50)
    change_reason: str | None = Field(default=None, max_length=500)


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
    file_type: str | None = None
    file_size: int | None = None
    description: str | None = None
    dof_id: int | None = None
    created_at: datetime
    tags: list[str] = []
    tag_labels: list[str] = []
    model_config = ConfigDict(from_attributes=True)


class RiskMediaTagsUpdate(BaseModel):
    selected: list[str] = []


class RiskRevisionResponse(BaseModel):
    id: int
    risk_id: int
    revision_no: int
    field_name: str | None
    old_value: str | None
    new_value: str | None
    change_reason: str | None
    changed_by_id: int | None
    changed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RiskResponse(BaseModel):
    id: int
    risk_code: str
    company_id: int
    branch_id: int | None
    department_id: int | None = None
    hazard_id: int
    method_code: str = "5x5_l"
    method_label: str | None = None
    method_formula: str | None = None
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
    probability: float
    frequency: float | None = None
    severity: float
    risk_score: float
    risk_level: str
    risk_level_label: str | None = None
    risk_action: str | None = None
    residual_probability: float | None = None
    residual_frequency: float | None = None
    residual_severity: float | None = None
    residual_score: float | None = None
    residual_level: str | None = None
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
    revisions: list[RiskRevisionResponse] = []
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
