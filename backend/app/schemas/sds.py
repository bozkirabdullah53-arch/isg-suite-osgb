"""0.9.119 — SDS/PKD kimyasal ürün sicili şemaları."""
from __future__ import annotations

from datetime import date, datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")


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

    model_config = ConfigDict(from_attributes=True)


class SdsDueSummary(BaseModel):
    total: int
    with_sds: int
    missing_sds: int
    due_soon: int
    overdue: int
