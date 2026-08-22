"""Yetkili firma kartı, belge ve profesyonel uygunluk giriş şemaları."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.input_rules import assert_meaningful_text, assert_person_name, clean_text


ReviewState = Literal["internal_record", "manually_reviewed"]
RequiredDocumentState = Literal["complete", "incomplete", "review_required"]
OnboardingStatus = Literal["draft", "in_progress", "completed"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _validate_range(start: date | None, end: date | None, label: str) -> None:
    if start and end and end < start:
        raise ValueError(f"{label} bitiş tarihi başlangıç tarihinden önce olamaz.")


class AuthorizedFirmCreate(StrictInput):
    osgb_id: int = Field(gt=0)
    company_id: int = Field(gt=0)
    firm_name: str | None = Field(default=None, max_length=220)
    is_active: bool = True
    firm_type: str | None = Field(default=None, max_length=80)
    province: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    authorized_representative: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    employee_count_declared: int | None = Field(default=None, ge=0)
    hazard_class: str | None = Field(default=None, max_length=40)
    authorization_scope: str | None = Field(default=None, max_length=2000)
    authorization_number: str | None = Field(default=None, max_length=100)
    authorization_issue_date: date | None = None
    authorization_start_date: date | None = None
    authorization_expiry_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    last_review_date: date | None = None
    review_state: ReviewState = "internal_record"

    @model_validator(mode="after")
    def sanitize(self):
        if self.firm_name is not None:
            self.firm_name = assert_meaningful_text(
                self.firm_name, label="Yetkili firma adı", min_len=2, required=True
            )
        self.firm_type = clean_text(self.firm_type)
        self.province = clean_text(self.province)
        self.district = clean_text(self.district)
        self.address = assert_meaningful_text(
            self.address, label="Adres", min_len=5, required=False
        )
        self.authorized_representative = assert_person_name(
            self.authorized_representative, label="Yetkili temsilci"
        )
        self.contact_phone = clean_text(self.contact_phone)
        self.hazard_class = clean_text(self.hazard_class)
        self.authorization_scope = assert_meaningful_text(
            self.authorization_scope, label="Yetki kapsamı", min_len=3, required=False
        )
        self.authorization_number = clean_text(self.authorization_number)
        self.notes = assert_meaningful_text(
            self.notes, label="Not", min_len=3, required=False
        )
        _validate_range(
            self.authorization_start_date,
            self.authorization_expiry_date,
            "Yetki",
        )
        if (
            self.authorization_issue_date
            and self.authorization_expiry_date
            and self.authorization_expiry_date < self.authorization_issue_date
        ):
            raise ValueError("Yetki bitiş tarihi düzenlenme tarihinden önce olamaz.")
        return self


class AuthorizedFirmUpdate(StrictInput):
    firm_name: str | None = Field(default=None, max_length=220)
    is_active: bool | None = None
    firm_type: str | None = Field(default=None, max_length=80)
    province: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    authorized_representative: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    employee_count_declared: int | None = Field(default=None, ge=0)
    hazard_class: str | None = Field(default=None, max_length=40)
    authorization_scope: str | None = Field(default=None, max_length=2000)
    authorization_number: str | None = Field(default=None, max_length=100)
    authorization_issue_date: date | None = None
    authorization_start_date: date | None = None
    authorization_expiry_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    last_review_date: date | None = None
    review_state: ReviewState | None = None

    @model_validator(mode="after")
    def sanitize(self):
        fields = set(self.model_fields_set)
        if "firm_name" in fields and self.firm_name is not None:
            self.firm_name = assert_meaningful_text(
                self.firm_name, label="Yetkili firma adı", min_len=2, required=True
            )
        if "firm_type" in fields:
            self.firm_type = clean_text(self.firm_type)
        if "province" in fields:
            self.province = clean_text(self.province)
        if "district" in fields:
            self.district = clean_text(self.district)
        if "address" in fields and self.address is not None:
            self.address = assert_meaningful_text(
                self.address, label="Adres", min_len=5, required=False
            )
        if "authorized_representative" in fields and self.authorized_representative is not None:
            self.authorized_representative = assert_person_name(
                self.authorized_representative, label="Yetkili temsilci"
            )
        if "contact_phone" in fields:
            self.contact_phone = clean_text(self.contact_phone)
        if "hazard_class" in fields:
            self.hazard_class = clean_text(self.hazard_class)
        if "authorization_scope" in fields and self.authorization_scope is not None:
            self.authorization_scope = assert_meaningful_text(
                self.authorization_scope, label="Yetki kapsamı", min_len=3, required=False
            )
        if "authorization_number" in fields:
            self.authorization_number = clean_text(self.authorization_number)
        if "notes" in fields and self.notes is not None:
            self.notes = assert_meaningful_text(
                self.notes, label="Not", min_len=3, required=False
            )
        return self


class AuthorizedFirmDocumentCreate(StrictInput):
    document_record_id: int | None = Field(default=None, gt=0)
    document_type: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=2, max_length=220)
    mandatory: bool = True
    start_date: date | None = None
    expiry_date: date | None = None
    review_date: date | None = None
    renewal_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @model_validator(mode="after")
    def sanitize(self):
        self.document_type = clean_text(self.document_type) or "genel"
        self.title = assert_meaningful_text(
            self.title, label="Belge adı", min_len=2, required=True
        )
        self.notes = assert_meaningful_text(
            self.notes, label="Belge notu", min_len=3, required=False
        )
        _validate_range(self.start_date, self.expiry_date, "Belge geçerlilik")
        _validate_range(self.review_date, self.renewal_date, "Belge yenileme")
        return self


class AuthorizedFirmDocumentUpdate(StrictInput):
    document_record_id: int | None = Field(default=None, gt=0)
    document_type: str | None = Field(default=None, min_length=2, max_length=80)
    title: str | None = Field(default=None, min_length=2, max_length=220)
    mandatory: bool | None = None
    start_date: date | None = None
    expiry_date: date | None = None
    review_date: date | None = None
    renewal_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @model_validator(mode="after")
    def sanitize(self):
        fields = set(self.model_fields_set)
        if "document_type" in fields:
            self.document_type = clean_text(self.document_type)
        if "title" in fields and self.title is not None:
            self.title = assert_meaningful_text(
                self.title, label="Belge adı", min_len=2, required=True
            )
        if "notes" in fields and self.notes is not None:
            self.notes = assert_meaningful_text(
                self.notes, label="Belge notu", min_len=3, required=False
            )
        return self


class ProfessionalComplianceUpsert(StrictInput):
    certificate_issue_date: date | None = None
    certificate_expiry_date: date | None = None
    document_review_date: date | None = None
    document_renewal_date: date | None = None
    required_documents_status: RequiredDocumentState = "review_required"
    required_documents_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_dates(self):
        _validate_range(
            self.certificate_issue_date,
            self.certificate_expiry_date,
            "Profesyonel belgesi",
        )
        _validate_range(
            self.document_review_date,
            self.document_renewal_date,
            "Profesyonel belge yenileme",
        )
        self.required_documents_note = assert_meaningful_text(
            self.required_documents_note,
            label="Zorunlu belge notu",
            min_len=3,
            required=False,
        )
        return self


class OnboardingProgressUpdate(StrictInput):
    current_step: int = Field(ge=1, le=11)
    completed_steps: list[int] = Field(default_factory=list, max_length=11)
    status: OnboardingStatus = "in_progress"

    @model_validator(mode="after")
    def normalize_steps(self):
        self.completed_steps = sorted({step for step in self.completed_steps if 1 <= step <= 11})
        if self.status == "completed" and self.completed_steps != list(range(1, 12)):
            raise ValueError("Onboarding tamamlandı sayılmadan önce 11 adımın tümü tamamlanmalıdır.")
        return self
