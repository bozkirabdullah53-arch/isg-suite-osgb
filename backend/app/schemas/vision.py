"""Saha fotoğrafı AI analiz şemaları (0.9.246).

/api/v1/risks/{risk_id}/media/{media_id}/analyze ve /analysis endpoint'leri
için Pydantic modelleri. Mevcut risk şemalarına dokunmaz.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VisionMevzuat(BaseModel):
    kanun: str | None = None
    madde: str | None = None
    yonetmelik: str | None = None
    standart: str | None = None
    tedbirler: list[str] = []
    onleyici_faaliyet: list[str] = []
    ceza_riski: dict[str, Any] | None = None


class VisionTermin(BaseModel):
    engine: str | None = None
    term_days: int | None = None
    term_date: str | None = None
    basis: str | None = None
    note: str | None = None


class VisionDofSuggestion(BaseModel):
    description: str
    type: str | None = None
    term_date: str | None = None
    source: str | None = None
    status: str | None = None


class VisionHazard(BaseModel):
    category: str
    severity: int
    confidence: float = 0.0
    bbox: list[float] = []
    note: str | None = None
    observed: str | None = None
    recommended_ppe: list[str] = []
    source_tag: str | None = None
    mevzuat: VisionMevzuat | None = None
    termin: VisionTermin | None = None
    dof_suggestions: list[VisionDofSuggestion] = []


class BboxAnnotation(BaseModel):
    label: str
    severity: int
    confidence: float = 0.0
    box: list[float] = []
    note: str | None = None


class VisionAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int | None = None
    media_id: int
    engine: str
    provider: str
    analyzed_at: str
    hazards: list[VisionHazard] = []
    bbox_annotations: list[BboxAnnotation] = []
    summary: str | None = None
    note: str | None = None
    created_at: datetime | None = None


class DofApplyRequest(BaseModel):
    """AI önerilen DÖF'leri gerçek DÖF kaydına dönüştürme isteği."""
    hazard_index: int = Field(0, ge=0)
    dof_index: int | None = None  # None ise o hazard'ın tüm DÖF'leri
