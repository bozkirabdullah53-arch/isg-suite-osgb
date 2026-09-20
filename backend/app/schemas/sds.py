"""0.9.119 — SDS/PKD kimyasal ürün sicili şemaları (+ 0.9.120 GHS checklist)."""
from __future__ import annotations

from datetime import date, datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
_PKD_STATUSES = {"draft", "active", "revision_pending", "archived"}
_ATMOSPHERE_TYPES = {"gas_vapour_mist", "dust", "mixed"}
_PKD_ZONES = {"zone_0", "zone_1", "zone_2", "zone_20", "zone_21", "zone_22"}


def _clean_list(values: list[str], *, max_items: int, max_length: int, field_name: str) -> list[str]:
    if len(values) > max_items:
        raise ValueError(f"{field_name} en fazla {max_items} seçenek içerebilir")
    cleaned: list[str] = []
    for item in values:
        value = str(item or "").strip()
        if not value:
            continue
        if len(value) > max_length:
            raise ValueError(f"{field_name} seçenekleri {max_length} karakteri geçemez")
        if value not in cleaned:
            cleaned.append(value)
    return cleaned


def _clean_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in _PKD_STATUSES:
        raise ValueError("PKD durumu geçersiz")
    return normalized


def _clean_atmosphere(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in _ATMOSPHERE_TYPES:
        raise ValueError("Patlayıcı ortam türü geçersiz")
    return normalized


def _clean_zones(values: list[str]) -> list[str]:
    cleaned = _clean_list(values, max_items=6, max_length=30, field_name="Zone sınıfları")
    invalid = [value for value in cleaned if value not in _PKD_ZONES]
    if invalid:
        raise ValueError("Zone sınıfı geçersiz")
    return cleaned


class ChemicalProductCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    product_name: str = Field(min_length=2, max_length=220)
    cas_number: str | None = Field(default=None, max_length=40)
    has_sds_file: bool = False
    next_review_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("product_name")
    @classmethod
    def _name(cls, v: str) -> str:
        s = (v or "").strip()
        if len(s) < 2:
            raise ValueError("Ürün adı en az 2 karakter olmalıdır")
        return s

    @field_validator("cas_number")
    @classmethod
    def _cas(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        if not _CAS_RE.match(s):
            raise ValueError("CAS numarası formatı geçersiz (örn. 67-64-1)")
        return s

    @field_validator("notes")
    @classmethod
    def _notes(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None


class ChemicalProductUpdate(BaseModel):
    product_name: str | None = Field(default=None, min_length=2, max_length=220)
    cas_number: str | None = Field(default=None, max_length=40)
    has_sds_file: bool | None = None
    next_review_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None

    @field_validator("product_name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if len(s) < 2:
            raise ValueError("Ürün adı en az 2 karakter olmalıdır")
        return s

    @field_validator("cas_number")
    @classmethod
    def _cas(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        if not _CAS_RE.match(s):
            raise ValueError("CAS numarası formatı geçersiz (örn. 67-64-1)")
        return s


class GhsChecklistUpdate(BaseModel):
    selected: list[str] = Field(default_factory=list, max_length=9)


class ChemicalProductResponse(BaseModel):
    id: int
    company_id: int
    branch_id: int | None = None
    product_name: str
    cas_number: str | None = None
    has_sds_file: bool
    document_id: int | None = None
    next_review_date: date | None = None
    notes: str | None = None
    is_active: bool
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    review_status: str | None = None
    ghs_selected: list[str] = Field(default_factory=list)
    ghs_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SdsDueSummary(BaseModel):
    total: int
    with_sds: int
    missing_sds: int
    due_soon: int
    overdue: int
    with_ghs_label: int = 0


class PkdDocumentCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    document_no: str = Field(min_length=2, max_length=80)
    area_name: str = Field(min_length=2, max_length=220)
    process_name: str | None = Field(default=None, max_length=220)
    atmosphere_type: str = "gas_vapour_mist"
    hazardous_materials: str | None = Field(default=None, max_length=1200)
    zone_classifications: list[str] = Field(default_factory=list, max_length=6)
    ignition_sources: list[str] = Field(default_factory=list, max_length=12)
    control_measures: list[str] = Field(default_factory=list, max_length=16)
    responsible_person: str | None = Field(default=None, max_length=160)
    prepared_by: str | None = Field(default=None, max_length=160)
    approved_by: str | None = Field(default=None, max_length=160)
    document_date: date | None = None
    revision_no: str | None = Field(default=None, max_length=30)
    next_review_date: date | None = None
    status: str = "draft"
    notes: str | None = Field(default=None, max_length=3000)

    @field_validator("document_no", "area_name", mode="before")
    @classmethod
    def _required_text(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if len(cleaned) < 2:
            raise ValueError("Bu alan en az 2 karakter olmalıdır")
        return cleaned

    @field_validator("process_name", "hazardous_materials", "responsible_person", "prepared_by", "approved_by", "revision_no", "notes", mode="before")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("atmosphere_type")
    @classmethod
    def _atmosphere(cls, value: str) -> str:
        return _clean_atmosphere(value)

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        return _clean_status(value)

    @field_validator("zone_classifications")
    @classmethod
    def _zones(cls, value: list[str]) -> list[str]:
        return _clean_zones(value)

    @field_validator("ignition_sources")
    @classmethod
    def _ignition_sources(cls, value: list[str]) -> list[str]:
        return _clean_list(value, max_items=12, max_length=80, field_name="Tutuşturucu kaynaklar")

    @field_validator("control_measures")
    @classmethod
    def _control_measures(cls, value: list[str]) -> list[str]:
        return _clean_list(value, max_items=16, max_length=140, field_name="Kontrol önlemleri")


class PkdDocumentUpdate(BaseModel):
    branch_id: int | None = None
    document_no: str | None = Field(default=None, min_length=2, max_length=80)
    area_name: str | None = Field(default=None, min_length=2, max_length=220)
    process_name: str | None = Field(default=None, max_length=220)
    atmosphere_type: str | None = None
    hazardous_materials: str | None = Field(default=None, max_length=1200)
    zone_classifications: list[str] | None = Field(default=None, max_length=6)
    ignition_sources: list[str] | None = Field(default=None, max_length=12)
    control_measures: list[str] | None = Field(default=None, max_length=16)
    responsible_person: str | None = Field(default=None, max_length=160)
    prepared_by: str | None = Field(default=None, max_length=160)
    approved_by: str | None = Field(default=None, max_length=160)
    document_date: date | None = None
    revision_no: str | None = Field(default=None, max_length=30)
    next_review_date: date | None = None
    status: str | None = None
    notes: str | None = Field(default=None, max_length=3000)
    is_active: bool | None = None

    @field_validator("document_no", "area_name", mode="before")
    @classmethod
    def _optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        if len(cleaned) < 2:
            raise ValueError("Bu alan en az 2 karakter olmalıdır")
        return cleaned

    @field_validator("process_name", "hazardous_materials", "responsible_person", "prepared_by", "approved_by", "revision_no", "notes", mode="before")
    @classmethod
    def _optional_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("atmosphere_type")
    @classmethod
    def _update_atmosphere(cls, value: str | None) -> str | None:
        return None if value is None else _clean_atmosphere(value)

    @field_validator("status")
    @classmethod
    def _update_status(cls, value: str | None) -> str | None:
        return None if value is None else _clean_status(value)

    @field_validator("zone_classifications")
    @classmethod
    def _update_zones(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_zones(value)

    @field_validator("ignition_sources")
    @classmethod
    def _update_ignition_sources(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_list(value, max_items=12, max_length=80, field_name="Tutuşturucu kaynaklar")

    @field_validator("control_measures")
    @classmethod
    def _update_control_measures(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_list(value, max_items=16, max_length=140, field_name="Kontrol önlemleri")


class PkdDocumentResponse(BaseModel):
    id: int
    company_id: int
    branch_id: int | None = None
    document_no: str
    area_name: str
    process_name: str | None = None
    atmosphere_type: str
    hazardous_materials: str | None = None
    zone_classifications: list[str] = Field(default_factory=list)
    ignition_sources: list[str] = Field(default_factory=list)
    control_measures: list[str] = Field(default_factory=list)
    responsible_person: str | None = None
    prepared_by: str | None = None
    approved_by: str | None = None
    document_date: date | None = None
    revision_no: str | None = None
    next_review_date: date | None = None
    status: str
    has_pkd_file: bool
    document_id: int | None = None
    notes: str | None = None
    is_active: bool
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    review_status: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PkdSummary(BaseModel):
    total: int
    active: int
    draft: int
    revision_pending: int
    with_file: int
    missing_file: int
    due_soon: int
    overdue: int
