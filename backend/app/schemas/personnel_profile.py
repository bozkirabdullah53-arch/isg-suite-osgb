"""Dijital Personel Kartı Faz 3 giriş şemaları.

Yalnız sıradan profesyonel bilgiler desteklenir. Restricted veya özel nitelikli veri
alanları bilerek tanımlanmamıştır ve extra='forbid' ile sessizce kabul edilmez.
"""
from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.input_rules import assert_meaningful_text, clean_text


SubjectType = Literal["employee", "professional"]
ContactType = Literal[
    "corporate_email",
    "alternative_email",
    "business_phone",
    "mobile_phone",
]
ContactVisibility = Literal["internal_only", "cv_eligible", "share_eligible"]
CompetencyCategory = Literal[
    "professional_duty",
    "certificate_based",
    "technical_specialization",
    "training_authority",
    "other",
]
ExperienceVisibility = Literal["internal_only", "cv_eligible"]


class StrictProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PersonnelProfileInitialize(StrictProfileInput):
    company_id: int = Field(gt=0)
    subject_type: SubjectType
    subject_id: int = Field(gt=0)
    branch_id: int | None = Field(default=None, gt=0)


class VersionedEntryInput(StrictProfileInput):
    entry_key: str | None = Field(default=None, max_length=36)
    change_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_version_request(self):
        if self.entry_key:
            try:
                UUID(self.entry_key)
            except (TypeError, ValueError) as exc:
                raise ValueError("Geçersiz sürüm kayıt anahtarı.") from exc
            if not clean_text(self.change_reason):
                raise ValueError("Yeni sürüm oluştururken değişiklik nedeni zorunludur.")
        self.change_reason = assert_meaningful_text(
            self.change_reason,
            label="Değişiklik nedeni",
            min_len=3,
            required=False,
        )
        return self


class PersonnelContactVersionCreate(VersionedEntryInput):
    contact_type: ContactType
    label: str | None = Field(default=None, max_length=100)
    contact_value: str = Field(min_length=3, max_length=320)
    is_primary: bool = False
    visibility: ContactVisibility = "internal_only"

    @model_validator(mode="after")
    def sanitize_contact(self):
        self.label = assert_meaningful_text(
            self.label, label="İletişim etiketi", min_len=2, required=False
        )
        value = clean_text(self.contact_value)
        if not value:
            raise ValueError("İletişim bilgisi zorunludur.")
        if self.contact_type in {"corporate_email", "alternative_email"}:
            self.contact_value = str(EmailStr._validate(value))
        else:
            digits = "".join(ch for ch in value if ch.isdigit())
            if len(digits) < 10 or len(digits) > 15:
                raise ValueError("Telefon numarası 10–15 rakam içermelidir.")
            self.contact_value = value
        return self


class PersonnelCompetencyVersionCreate(VersionedEntryInput):
    category: CompetencyCategory
    name: str = Field(min_length=2, max_length=220)
    start_date: date | None = None
    end_date: date | None = None
    certificate_number: str | None = Field(default=None, max_length=120)
    issuing_organization: str | None = Field(default=None, max_length=220)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def sanitize_competency(self):
        self.name = assert_meaningful_text(
            self.name, label="Yeterlilik adı", min_len=2, required=True
        )
        self.certificate_number = clean_text(self.certificate_number)
        self.issuing_organization = assert_meaningful_text(
            self.issuing_organization,
            label="Veren kuruluş",
            min_len=2,
            required=False,
        )
        self.description = assert_meaningful_text(
            self.description,
            label="Yeterlilik açıklaması",
            min_len=3,
            required=False,
        )
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Yeterlilik bitiş tarihi başlangıç tarihinden önce olamaz.")
        return self


class PersonnelExperienceVersionCreate(VersionedEntryInput):
    organization_name: str = Field(min_length=2, max_length=220)
    position: str = Field(min_length=2, max_length=180)
    start_date: date | None = None
    end_date: date | None = None
    employment_type: str | None = Field(default=None, max_length=80)
    sector: str | None = Field(default=None, max_length=160)
    nace_activity: str | None = Field(default=None, max_length=300)
    project_name: str | None = Field(default=None, max_length=220)
    professional_summary: str | None = Field(default=None, max_length=2000)
    responsibilities: str | None = Field(default=None, max_length=5000)
    visibility: ExperienceVisibility = "internal_only"

    @model_validator(mode="after")
    def sanitize_experience(self):
        self.organization_name = assert_meaningful_text(
            self.organization_name,
            label="Kurum adı",
            min_len=2,
            required=True,
        )
        self.position = assert_meaningful_text(
            self.position, label="Pozisyon", min_len=2, required=True
        )
        self.employment_type = clean_text(self.employment_type)
        self.sector = clean_text(self.sector)
        self.nace_activity = clean_text(self.nace_activity)
        self.project_name = assert_meaningful_text(
            self.project_name, label="Proje adı", min_len=2, required=False
        )
        self.professional_summary = assert_meaningful_text(
            self.professional_summary,
            label="Profesyonel deneyim özeti",
            min_len=5,
            required=False,
        )
        self.responsibilities = assert_meaningful_text(
            self.responsibilities,
            label="Sorumluluk özeti",
            min_len=5,
            required=False,
        )
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Deneyim bitiş tarihi başlangıç tarihinden önce olamaz.")
        return self
