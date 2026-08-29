from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator


class VisitorPassCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: int = Field(gt=0)
    full_name: str = Field(min_length=2, max_length=160)
    organization: str | None = Field(default=None, max_length=220)
    phone: str | None = Field(default=None, max_length=40)
    purpose: str = Field(min_length=3, max_length=500)
    valid_from: datetime
    valid_until: datetime
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def valid_range(self):
        if self.valid_until <= self.valid_from:
            raise ValueError("Geçiş bitişi başlangıçtan sonra olmalıdır.")
        self.full_name = self.full_name.strip()
        self.purpose = self.purpose.strip()
        return self
