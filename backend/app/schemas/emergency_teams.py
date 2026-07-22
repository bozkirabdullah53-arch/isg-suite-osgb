"""0.9.134 — Acil durum ekipleri / destek elemanları şemaları (İSG uzmanı)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Sistem varsayılan ekip türleri (6331 / 6 fonksiyon)
DEFAULT_TEAM_TYPES: tuple[tuple[str, str], ...] = (
    ("sondurme", "Söndürme Ekibi"),
    ("kurtarma", "Kurtarma Ekibi"),
    ("koruma", "Koruma Ekibi"),
    ("ilk_yardim", "İlk Yardım Ekibi"),
    ("tahliye", "Tahliye Ekibi"),
    ("haberlesme", "Haberleşme Ekibi"),
)

MEMBERSHIPS = ("asil", "yedek")
CERT_STATUSES = ("green", "yellow", "red", "grey")


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


# --------------------------------------------------------------------------- #
# Team types
# --------------------------------------------------------------------------- #
class TeamTypeResponse(BaseModel):
    id: int
    company_id: int | None
    code: str
    name: str
    is_system: bool
    min_members: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Teams
# --------------------------------------------------------------------------- #
class TeamCreate(BaseModel):
    company_id: int
    type_id: int
    name: str = Field(min_length=2, max_length=160)
    min_members: int | None = Field(default=None, ge=0, le=1000)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        s = (v or "").strip()
        if len(s) < 2:
            raise ValueError("Ekip adı en az 2 karakter olmalıdır")
        return s

    @field_validator("notes")
    @classmethod
    def _notes(cls, v: str | None) -> str | None:
        return _clean(v)


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    type_id: int | None = None
    min_members: int | None = Field(default=None, ge=0, le=1000)
    notes: str | None = Field(default=None, max_length=2000)
    leader_assignment_id: int | None = None


class TeamStatus(BaseModel):
    code: str  # tam | eksik | kritik | guncelleme
    label: str
    tone: str  # ok | warn | danger | muted


class TeamResponse(BaseModel):
    id: int
    company_id: int
    type_id: int
    type_code: str | None = None
    type_name: str | None = None
    name: str
    min_members: int
    notes: str | None
    leader_assignment_id: int | None
    leader_name: str | None = None
    member_count: int = 0
    asil_count: int = 0
    yedek_count: int = 0
    cert_summary: dict[str, int] = Field(default_factory=dict)
    status: TeamStatus | None = None
    warnings: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Assignments (üyeler / destek elemanları)
# --------------------------------------------------------------------------- #
class AssignmentCreate(BaseModel):
    company_id: int
    team_id: int
    employee_id: int
    membership: str = "asil"
    is_leader: bool = False
    role_title: str | None = Field(default=None, max_length=120)
    shift: str | None = Field(default=None, max_length=60)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    section: str | None = Field(default=None, max_length=120)
    personnel_no: str | None = Field(default=None, max_length=60)
    assign_start: date | None = None
    assign_end: date | None = None
    letter_date: date | None = None
    letter_no: str | None = Field(default=None, max_length=60)
    assigned_by: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("membership")
    @classmethod
    def _membership(cls, v: str) -> str:
        s = (v or "asil").strip().lower()
        if s not in MEMBERSHIPS:
            raise ValueError("Üyelik türü asil veya yedek olmalıdır")
        return s

    @field_validator(
        "role_title", "shift", "phone", "email", "section",
        "personnel_no", "letter_no", "assigned_by", "notes",
    )
    @classmethod
    def _opt(cls, v: str | None) -> str | None:
        return _clean(v)


class AssignmentUpdate(BaseModel):
    team_id: int | None = None
    membership: str | None = None
    is_leader: bool | None = None
    role_title: str | None = Field(default=None, max_length=120)
    shift: str | None = Field(default=None, max_length=60)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    section: str | None = Field(default=None, max_length=120)
    personnel_no: str | None = Field(default=None, max_length=60)
    assign_start: date | None = None
    assign_end: date | None = None
    letter_date: date | None = None
    letter_no: str | None = Field(default=None, max_length=60)
    assigned_by: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("membership")
    @classmethod
    def _membership(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip().lower()
        if s not in MEMBERSHIPS:
            raise ValueError("Üyelik türü asil veya yedek olmalıdır")
        return s


class TrainingResponse(BaseModel):
    id: int
    assignment_id: int
    training_type: str | None
    provider: str | None
    trainer: str | None
    training_date: date | None
    duration_hours: float | None
    certificate_no: str | None
    valid_until: date | None
    file_path: str | None
    first_aid_cert_no: str | None
    first_aid_center: str | None
    first_aid_start: date | None
    first_aid_end: date | None
    refresh_date: date | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingCreate(BaseModel):
    training_type: str | None = Field(default=None, max_length=120)
    provider: str | None = Field(default=None, max_length=160)
    trainer: str | None = Field(default=None, max_length=160)
    training_date: date | None = None
    duration_hours: float | None = Field(default=None, ge=0, le=10000)
    certificate_no: str | None = Field(default=None, max_length=80)
    valid_until: date | None = None
    first_aid_cert_no: str | None = Field(default=None, max_length=80)
    first_aid_center: str | None = Field(default=None, max_length=160)
    first_aid_start: date | None = None
    first_aid_end: date | None = None
    refresh_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AssignmentResponse(BaseModel):
    id: int
    company_id: int
    team_id: int
    team_name: str | None = None
    employee_id: int
    employee_name: str | None = None
    membership: str
    is_leader: bool
    role_title: str | None
    shift: str | None
    phone: str | None
    email: str | None
    section: str | None
    personnel_no: str | None
    assign_start: date | None
    assign_end: date | None
    letter_date: date | None
    letter_no: str | None
    assigned_by: str | None
    notes: str | None
    cert_status: str = "grey"
    cert_valid_until: date | None = None
    training_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
