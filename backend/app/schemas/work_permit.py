from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PERMIT_TYPES = {"hot_work", "work_at_height", "confined_space", "electrical", "general"}
PERMIT_STATUSES = {"draft", "pending_approval", "active", "suspended", "expired", "closed", "rejected", "cancelled"}


class WorkPermitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: int = Field(gt=0)
    permit_type: str
    description: str = Field(min_length=3, max_length=5000)
    location: str = Field(min_length=2, max_length=300)
    valid_from: datetime
    valid_until: datetime
    employee_ids: list[int] = Field(default_factory=list, max_length=100)
    risk_id: int | None = Field(default=None, gt=0)
    incident_id: int | None = Field(default=None, gt=0)
    dof_id: int | None = Field(default=None, gt=0)
    field_inspection_id: int | None = Field(default=None, gt=0)
    contractor_id: int | None = Field(default=None, gt=0)
    approver_user_ids: list[int] = Field(default_factory=list, max_length=10)
    client_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("permit_type")
    @classmethod
    def valid_type(cls, value: str):
        value = value.strip().lower()
        if value not in PERMIT_TYPES:
            raise ValueError("Geçersiz çalışma izni türü.")
        return value

    @model_validator(mode="after")
    def valid_range(self):
        if self.valid_until <= self.valid_from:
            raise ValueError("Geçerlilik bitişi başlangıçtan sonra olmalıdır.")
        self.employee_ids = sorted({item for item in self.employee_ids if item > 0})
        self.approver_user_ids = list(dict.fromkeys(item for item in self.approver_user_ids if item > 0))
        self.description, self.location = self.description.strip(), self.location.strip()
        return self


class WorkPermitStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, max_length=2000)


class WorkPermitControlInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    control_type: str = Field(min_length=2, max_length=50)
    status: str = "pending"
    details: str | None = Field(default=None, max_length=3000)
    measured_value: str | None = Field(default=None, max_length=80)
    unit: str | None = Field(default=None, max_length=30)

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str):
        value = value.strip().lower()
        if value not in {"pending", "passed", "failed", "not_applicable"}:
            raise ValueError("Geçersiz kontrol durumu.")
        return value


class WorkPermitExtension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valid_until: datetime
    note: str = Field(min_length=3, max_length=2000)
