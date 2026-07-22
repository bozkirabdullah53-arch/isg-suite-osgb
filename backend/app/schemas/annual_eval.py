"""0.9.135 — Yıllık plan değerlendirme şemaları (plan kalemleri salt okunur)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

OUTCOME_STATUSES = (
    "planlandi",
    "devam",
    "tamam",
    "kismi",
    "gecikmeli_tamam",
    "ertelendi",
    "gerceklesmedi",
    "iptal",
    "plan_revizyonuyla_kaldirildi",
)
REPORT_STATUSES = (
    "hazirlanmadi",
    "hazirlaniyor",
    "uzman_tamam",
    "hekim_bekliyor",
    "isveren_bekliyor",
    "onaylandi",
    "revizyon",
    "arsiv",
)
LOCKED_REPORT = frozenset({"onaylandi", "arsiv"})
EXCLUDED_FROM_RATE = frozenset({"iptal", "plan_revizyonuyla_kaldirildi"})


class AnnualEvalStart(BaseModel):
    company_id: int
    year: int = Field(ge=2020, le=2100)


class AnnualEvalItemUpdate(BaseModel):
    outcome_status: str | None = None
    actual_start: date | None = None
    actual_end: date | None = None
    completion_pct: int | None = Field(default=None, ge=0, le=100)
    result_text: str | None = Field(default=None, max_length=4000)
    deviation_reason: str | None = Field(default=None, max_length=2000)
    specialist_note: str | None = Field(default=None, max_length=2000)
    physician_note: str | None = Field(default=None, max_length=2000)
    employer_note: str | None = Field(default=None, max_length=2000)
    next_year_suggestion: str | None = Field(default=None, max_length=2000)
    target_met: bool | None = None
    capa_needed: bool | None = None

    @field_validator("outcome_status")
    @classmethod
    def _outcome(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if s not in OUTCOME_STATUSES:
            raise ValueError("Geçersiz gerçekleşme durumu")
        return s


class UnplannedCreate(BaseModel):
    activity: str = Field(min_length=3, max_length=240)
    category: str | None = Field(default=None, max_length=40)
    done_date: date | None = None
    reason: str | None = Field(default=None, max_length=2000)
    result_text: str | None = Field(default=None, max_length=4000)
    responsible_name: str | None = Field(default=None, max_length=160)
    suggest_next_year: bool = False


class CapaCreate(BaseModel):
    evaluation_item_id: int | None = None
    title: str = Field(min_length=3, max_length=240)
    root_cause: str | None = Field(default=None, max_length=2000)
    action: str | None = Field(default=None, max_length=2000)
    responsible: str | None = Field(default=None, max_length=160)
    due_date: date | None = None
    priority: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)


class TransferNextYearItem(BaseModel):
    activity: str = Field(min_length=3, max_length=240)
    category: str | None = Field(default=None, max_length=40)
    month: int = Field(default=1, ge=1, le=12)
    responsible_name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    source_eval_item_id: int | None = None
    source_unplanned_id: int | None = None


class TransferNextYear(BaseModel):
    company_id: int
    from_year: int = Field(ge=2020, le=2100)
    items: list[TransferNextYearItem] = Field(min_length=1)


class EvidenceLinkCreate(BaseModel):
    source_module: str = Field(min_length=2, max_length=40)
    source_id: int
    title: str | None = Field(default=None, max_length=200)
    doc_type: str | None = Field(default="modul_link", max_length=80)


class BulkEvalAction(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=200)
    action: str  # note | suggest_next | mark_capa | complete
    specialist_note: str | None = Field(default=None, max_length=2000)
    next_year_suggestion: str | None = Field(default=None, max_length=2000)
    actual_end: date | None = None
    result_text: str | None = Field(default=None, max_length=4000)


class PlanItemSnapshot(BaseModel):
    id: int
    activity: str
    category: str | None
    month: int
    target_date: date | None
    responsible_name: str | None
    description: str | None
    plan_status: str


class EvalItemResponse(BaseModel):
    id: int
    evaluation_id: int
    plan_item_id: int
    company_id: int
    year: int
    outcome_status: str
    actual_start: date | None
    actual_end: date | None
    completion_pct: int | None
    result_text: str | None
    deviation_reason: str | None
    delay_days: int | None
    specialist_note: str | None
    physician_note: str | None
    employer_note: str | None
    next_year_suggestion: str | None
    target_met: bool | None
    capa_needed: bool
    evidence_count: int = 0
    plan: PlanItemSnapshot
    model_config = ConfigDict(from_attributes=True)


class EvalOverviewResponse(BaseModel):
    evaluation_id: int | None
    company_id: int
    year: int
    report_status: str
    company_name: str | None = None
    sgk_registry_no: str | None = None
    address: str | None = None
    hazard_class: str | None = None
    employee_count: int = 0
    plan_item_count: int = 0
    plan_item_count_at_start: int = 0
    plan_count_warning: str | None = None
    kpis: dict
    warnings: list[str] = []
