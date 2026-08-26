"""Görsel saha denetimi API sözleşmeleri."""
from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _clean_list(values: list[Any] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        clean = _clean(str(value))
        if clean and clean not in result:
            result.append(clean)
    return result


class FieldBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SiteCreate(FieldBase):
    company_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=220)
    site_type: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def clean(self):
        self.name = self.name.strip()
        self.site_type, self.address, self.description = map(_clean, (self.site_type, self.address, self.description))
        return self


class AreaCreate(FieldBase):
    company_id: int = Field(gt=0)
    site_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=220)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def clean(self):
        self.name = self.name.strip()
        self.description = _clean(self.description)
        return self


class EquipmentCreate(FieldBase):
    company_id: int = Field(gt=0)
    site_id: int = Field(gt=0)
    area_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=220)
    equipment_type: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def clean(self):
        self.name = self.name.strip()
        self.equipment_type, self.description = map(_clean, (self.equipment_type, self.description))
        return self


class FieldHazardCreate(FieldBase):
    company_id: int = Field(gt=0)
    category_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=220)
    description: str | None = Field(default=None, max_length=2000)
    equipment_scope: str | None = Field(default=None, max_length=220)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    scope: str = Field(default="company", max_length=20)
    is_active: bool = True

    @model_validator(mode="after")
    def clean(self):
        self.name = self.name.strip()
        self.description, self.equipment_scope = map(_clean, (self.description, self.equipment_scope))
        self.keywords = _clean_list(self.keywords)
        if self.scope not in {"company", "osgb"}:
            raise ValueError("Tehlike kapsamı company veya osgb olmalıdır.")
        return self


class FieldHazardUpdate(FieldBase):
    description: str | None = Field(default=None, max_length=2000)
    equipment_scope: str | None = Field(default=None, max_length=220)
    keywords: list[str] | None = Field(default=None, max_length=30)
    is_active: bool | None = None

    @model_validator(mode="after")
    def clean(self):
        self.description, self.equipment_scope = map(_clean, (self.description, self.equipment_scope))
        if self.keywords is not None:
            self.keywords = _clean_list(self.keywords)
        return self


class GpsPayload(FieldBase):
    gps_lat: float | None = Field(default=None, ge=-90, le=90)
    gps_lng: float | None = Field(default=None, ge=-180, le=180)
    gps_accuracy_m: float | None = Field(default=None, ge=0, le=100000)
    gps_captured_at: datetime | None = None
    gps_status: str = Field(default="not_available", max_length=30)
    gps_provider: str | None = Field(default=None, max_length=60)
    gps_reason: str | None = Field(default=None, max_length=500)
    manual_location_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_gps(self):
        self.gps_provider, self.gps_reason, self.manual_location_note = map(
            _clean, (self.gps_provider, self.gps_reason, self.manual_location_note)
        )
        for value in (self.gps_lat, self.gps_lng, self.gps_accuracy_m):
            if value is not None and not math.isfinite(value):
                raise ValueError("GPS sayısal değerleri geçerli olmalıdır.")
        if self.gps_status not in {"captured", "low_accuracy", "denied", "unavailable", "not_available", "manual"}:
            raise ValueError("GPS durumu geçersiz.")
        has_coordinates = self.gps_lat is not None or self.gps_lng is not None
        if has_coordinates and (self.gps_lat is None or self.gps_lng is None):
            raise ValueError("Enlem ve boylam birlikte gönderilmelidir.")
        if has_coordinates and self.gps_status not in {"captured", "low_accuracy"}:
            raise ValueError("Koordinat varsa GPS durumu captured veya low_accuracy olmalıdır.")
        if not has_coordinates and self.gps_status in {"captured", "low_accuracy"}:
            raise ValueError("Koordinat yokken GPS captured olamaz.")
        return self


class FieldInspectionCreate(GpsPayload):
    company_id: int = Field(gt=0)
    site_id: int = Field(gt=0)
    area_id: int = Field(gt=0)
    equipment_id: int | None = Field(default=None, gt=0)
    inspection_date: date | None = None
    inspection_at: datetime | None = None
    timezone: str = Field(default="Europe/Istanbul", min_length=3, max_length=80)
    selected_category_ids: list[int] = Field(default_factory=list, max_length=75)
    selected_hazard_ids: list[int] = Field(default_factory=list, max_length=100)
    scan_all_hazards: bool = True
    notes: str | None = Field(default=None, max_length=5000)
    client_reference: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def clean(self):
        self.selected_category_ids = sorted({int(value) for value in self.selected_category_ids if int(value) > 0})
        self.selected_hazard_ids = sorted({int(value) for value in self.selected_hazard_ids if int(value) > 0})
        self.notes, self.client_reference = map(_clean, (self.notes, self.client_reference))
        return self


class FieldInspectionUpdate(FieldBase):
    site_id: int | None = Field(default=None, gt=0)
    area_id: int | None = Field(default=None, gt=0)
    equipment_id: int | None = Field(default=None, gt=0)
    inspection_date: date | None = None
    inspection_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, max_length=40)
    selected_category_ids: list[int] | None = Field(default=None, max_length=75)
    selected_hazard_ids: list[int] | None = Field(default=None, max_length=100)
    scan_all_hazards: bool | None = None

    @field_validator("timezone", "notes", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _clean(value)


class GpsUpdate(GpsPayload):
    pass


class ManualFindingCreate(FieldBase):
    photo_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    hazard_id: int | None = Field(default=None, gt=0)
    hazard_name: str = Field(min_length=2, max_length=220)
    visual_evidence: str = Field(min_length=3, max_length=4000)
    nonconformity_description: str = Field(min_length=3, max_length=4000)
    possible_cause: str | None = Field(default=None, max_length=3000)
    possible_harm: str | None = Field(default=None, max_length=3000)
    possible_accident_or_disease: str | None = Field(default=None, max_length=3000)
    suggested_priority: str = Field(default="medium", max_length=30)
    priority_reason: str | None = Field(default=None, max_length=2000)
    urgent_action: str | None = Field(default=None, max_length=3000)
    corrective_action: str | None = Field(default=None, max_length=3000)
    preventive_action: str | None = Field(default=None, max_length=3000)
    suggested_responsible_role: str | None = Field(default=None, max_length=180)
    suggested_term_date: date | None = None

    @model_validator(mode="after")
    def clean(self):
        self.hazard_name = self.hazard_name.strip()
        for field in (
            "visual_evidence", "nonconformity_description", "possible_cause", "possible_harm",
            "possible_accident_or_disease", "priority_reason", "urgent_action", "corrective_action",
            "preventive_action", "suggested_responsible_role",
        ):
            setattr(self, field, _clean(getattr(self, field)))
        if self.suggested_priority not in {"low", "medium", "high", "critical"}:
            raise ValueError("Bulgu önceliği geçersiz.")
        return self


class FindingReview(FieldBase):
    status: str = Field(max_length=40)
    hazard_name: str | None = Field(default=None, min_length=2, max_length=220)
    visual_evidence: str | None = Field(default=None, min_length=3, max_length=4000)
    nonconformity_description: str | None = Field(default=None, min_length=3, max_length=4000)
    possible_cause: str | None = Field(default=None, max_length=3000)
    possible_harm: str | None = Field(default=None, max_length=3000)
    possible_accident_or_disease: str | None = Field(default=None, max_length=3000)
    suggested_priority: str | None = Field(default=None, max_length=30)
    priority_reason: str | None = Field(default=None, max_length=2000)
    urgent_action: str | None = Field(default=None, max_length=3000)
    corrective_action: str | None = Field(default=None, max_length=3000)
    preventive_action: str | None = Field(default=None, max_length=3000)
    engineering_control: str | None = Field(default=None, max_length=3000)
    administrative_control: str | None = Field(default=None, max_length=3000)
    training_need: str | None = Field(default=None, max_length=2000)
    required_ppe: str | None = Field(default=None, max_length=2000)
    suggested_responsible_role: str | None = Field(default=None, max_length=180)
    suggested_term_date: date | None = None
    review_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_review(self):
        allowed = {"under_review", "accepted", "rejected", "not_verifiable", "corrected", "superseded"}
        if self.status not in allowed:
            raise ValueError("Bulgu inceleme durumu geçersiz.")
        if self.suggested_priority is not None and self.suggested_priority not in {"low", "medium", "high", "critical"}:
            raise ValueError("Bulgu önceliği geçersiz.")
        for field in self.model_fields:
            if field not in {"status", "suggested_term_date", "suggested_priority"}:
                value = getattr(self, field)
                if isinstance(value, str):
                    setattr(self, field, value.strip() or None)
        return self


class AnnotationCreate(FieldBase):
    photo_id: int = Field(gt=0)
    finding_id: int | None = Field(default=None, gt=0)
    shape_type: str = Field(default="rectangle", max_length=30)
    x: float = Field(default=0, ge=0, le=1)
    y: float = Field(default=0, ge=0, le=1)
    width: float = Field(default=0, ge=0, le=1)
    height: float = Field(default=0, ge=0, le=1)
    points: list[list[float]] = Field(default_factory=list, max_length=100)
    label: str | None = Field(default=None, max_length=220)
    color: str = Field(default="#dc2626", max_length=20)

    @model_validator(mode="after")
    def validate_shape(self):
        if self.shape_type not in {"rectangle", "arrow", "point", "polygon", "region"}:
            raise ValueError("İşaret şekli geçersiz.")
        if self.shape_type == "polygon" and len(self.points) < 3:
            raise ValueError("Poligon için en az üç nokta gerekir.")
        for point in self.points:
            if len(point) != 2 or not all(0 <= float(value) <= 1 for value in point):
                raise ValueError("İşaret noktaları 0 ile 1 arasında olmalıdır.")
        self.label = _clean(self.label)
        return self


class AnnotationUpdate(FieldBase):
    shape_type: str | None = Field(default=None, max_length=30)
    x: float | None = Field(default=None, ge=0, le=1)
    y: float | None = Field(default=None, ge=0, le=1)
    width: float | None = Field(default=None, ge=0, le=1)
    height: float | None = Field(default=None, ge=0, le=1)
    points: list[list[float]] | None = Field(default=None, max_length=100)
    label: str | None = Field(default=None, max_length=220)
    color: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def validate_shape(self):
        if self.shape_type is not None and self.shape_type not in {"rectangle", "arrow", "point", "polygon", "region"}:
            raise ValueError("İşaret şekli geçersiz.")
        if self.points is not None:
            if self.shape_type == "polygon" and len(self.points) < 3:
                raise ValueError("Poligon için en az üç nokta gerekir.")
            for point in self.points:
                if len(point) != 2 or not all(0 <= float(value) <= 1 for value in point):
                    raise ValueError("İşaret noktaları 0 ile 1 arasında olmalıdır.")
        self.label = _clean(self.label)
        return self


class ActionCreate(FieldBase):
    finding_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=2, max_length=300)
    activity: str = Field(min_length=3, max_length=5000)
    urgent_action: str | None = Field(default=None, max_length=3000)
    permanent_solution: str | None = Field(default=None, max_length=3000)
    preventive_action: str | None = Field(default=None, max_length=3000)
    responsible_employee_id: int | None = Field(default=None, gt=0)
    responsible_person: str | None = Field(default=None, max_length=180)
    responsible_role: str | None = Field(default=None, max_length=180)
    term_date: date | None = None
    priority: str = Field(default="medium", max_length=30)
    notes: str | None = Field(default=None, max_length=3000)
    evidence_photo_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def clean(self):
        self.title, self.activity = self.title.strip(), self.activity.strip()
        for field in ("urgent_action", "permanent_solution", "preventive_action", "responsible_person", "responsible_role", "notes"):
            setattr(self, field, _clean(getattr(self, field)))
        if self.priority not in {"low", "medium", "high", "critical"}:
            raise ValueError("Faaliyet önceliği geçersiz.")
        if not self.responsible_employee_id and not self.responsible_person and not self.responsible_role:
            raise ValueError("Sorumlu kişi, çalışan veya rolü belirtilmelidir.")
        return self


class ActionUpdate(FieldBase):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    activity: str | None = Field(default=None, min_length=3, max_length=5000)
    responsible_employee_id: int | None = Field(default=None, gt=0)
    responsible_person: str | None = Field(default=None, max_length=180)
    responsible_role: str | None = Field(default=None, max_length=180)
    term_date: date | None = None
    priority: str | None = Field(default=None, max_length=30)
    status: str | None = Field(default=None, max_length=30)
    completion_date: date | None = None
    notes: str | None = Field(default=None, max_length=3000)


class LegalReferenceInput(FieldBase):
    regulation_name: str = Field(min_length=3, max_length=300)
    article: str | None = Field(default=None, max_length=120)
    paragraph: str | None = Field(default=None, max_length=120)
    source_url: str | None = Field(default=None, max_length=600)
    source_version: str | None = Field(default=None, max_length=120)
    relation_explanation: str | None = Field(default=None, max_length=2000)
    verification_status: str = Field(default="needs_expert_review", max_length=30)

    @model_validator(mode="after")
    def clean(self):
        for field in self.model_fields:
            value = getattr(self, field)
            if isinstance(value, str):
                setattr(self, field, value.strip() or None)
        if self.verification_status not in {"needs_expert_review", "verified", "rejected"}:
            raise ValueError("Mevzuat doğrulama durumu geçersiz.")
        return self


class LegalReferenceUpdate(FieldBase):
    references: list[LegalReferenceInput] = Field(default_factory=list, max_length=20)


class ApprovalPayload(FieldBase):
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note", mode="before")
    @classmethod
    def strip_note(cls, value):
        return _clean(value)
