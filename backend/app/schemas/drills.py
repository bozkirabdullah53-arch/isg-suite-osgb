"""0.9.131 — Tatbikat yönetimi şemaları (İSG uzmanı)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

DRILL_TYPES = (
    "Yangın",
    "Deprem",
    "Tahliye",
    "Kimyasal Sızıntı",
    "Patlama / Acil Durum",
    "İlk Yardım",
    "Kurtarma",
    "Diğer",
)
DRILL_STATUSES = ("planlandi", "yapildi", "eksik", "iptal")


class DrillParticipant(BaseModel):
    id: int | None = None
    full_name: str
    job_title: str | None = None
    department: str | None = None


class DrillPhotoResponse(BaseModel):
    id: int
    storage_path: str
    original_name: str | None
    content_type: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DrillCreate(BaseModel):
    company_id: int
    drill_type: str = Field(min_length=2, max_length=80)
    drill_date: date
    start_time: str | None = Field(default=None, max_length=10)
    end_time: str | None = Field(default=None, max_length=10)
    responsible: str | None = Field(default=None, max_length=200)
    participant_count: int | None = Field(default=None, ge=0, le=100000)
    assembly_area: str | None = Field(default=None, max_length=300)
    status: str = "planlandi"
    scenario: str = Field(min_length=2, max_length=10000)
    gaps: str | None = Field(default=None, max_length=10000)
    result: str | None = Field(default=None, max_length=10000)
    employee_ids: list[int] = Field(default_factory=list)

    @field_validator("drill_type")
    @classmethod
    def _type(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in DRILL_TYPES:
            raise ValueError("Geçersiz tatbikat türü")
        return s

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        s = (v or "").strip().lower()
        if s not in DRILL_STATUSES:
            raise ValueError("Geçersiz durum")
        return s

    @field_validator("scenario")
    @classmethod
    def _scenario(cls, v: str) -> str:
        s = (v or "").strip()
        if len(s) < 2:
            raise ValueError("Senaryo en az 2 karakter olmalıdır")
        return s

    @field_validator("responsible", "assembly_area", "gaps", "result", "start_time", "end_time")
    @classmethod
    def _opt(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None


class DrillResponse(BaseModel):
    id: int
    company_id: int
    drill_type: str
    drill_date: date
    start_time: str | None
    end_time: str | None
    responsible: str | None
    participant_count: int
    assembly_area: str | None
    status: str
    scenario: str
    gaps: str | None
    result: str | None
    participants: list[DrillParticipant]
    photos: list[DrillPhotoResponse]
    is_active: bool
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
