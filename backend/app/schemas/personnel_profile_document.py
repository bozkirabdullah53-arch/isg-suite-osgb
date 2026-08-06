"""Dijital Personel Kartı sıradan belge/CV işlemleri için dar şemalar."""
from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.input_rules import assert_meaningful_text


DocumentKind = Literal["profile_photo", "cv", "qualification", "certificate"]
DocumentCategory = Literal[
    "profile_photo",
    "cv",
    "diploma",
    "graduation_certificate",
    "occupational_safety_certificate",
    "workplace_physician_certificate",
    "other_health_personnel_certificate",
    "trainer_certificate",
    "myk_certificate",
    "mastership_certificate",
    "journeyman_certificate",
    "operator_certificate",
    "first_aid_certificate",
    "working_at_height_certificate",
    "fire_safety_certificate",
    "emergency_response_certificate",
    "explosion_protection_certificate",
    "risk_assessment_certificate",
    "electrical_work_certificate",
    "scaffolding_certificate",
    "welding_certificate",
    "hygiene_certificate",
    "language_certificate",
    "other_professional_document",
]
DocumentAccess = Literal["internal_only", "cv_eligible", "share_eligible"]


class PersonnelProfileDocumentMetadata(BaseModel):
    """Multipart form alanlarını servis sınırında yeniden doğrular."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_kind: DocumentKind
    category: DocumentCategory
    title: str = Field(min_length=2, max_length=220)
    document_key: UUID | None = None
    document_number: str | None = Field(default=None, max_length=120)
    issuing_organization: str | None = Field(default=None, max_length=220)
    issue_date: date | None = None
    valid_from: date | None = None
    expiration_date: date | None = None
    no_expiration: bool = False
    access_classification: DocumentAccess = "internal_only"
    change_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_metadata(self):
        self.title = assert_meaningful_text(
            self.title,
            label="Belge başlığı",
            min_len=2,
            required=True,
        )
        if self.document_kind == "profile_photo" and self.category != "profile_photo":
            raise ValueError("Profil fotoğrafı yalnız profile_photo kategorisinde olabilir.")
        if self.document_kind == "cv" and self.category != "cv":
            raise ValueError("CV yalnız cv kategorisinde olabilir.")
        if self.document_kind in {"qualification", "certificate"} and self.category in {
            "profile_photo",
            "cv",
        }:
            raise ValueError("Yeterlilik/sertifika kategorisi belge türüyle uyumlu değil.")
        if self.no_expiration and self.expiration_date is not None:
            raise ValueError("Süresiz belgede son geçerlilik tarihi bulunamaz.")
        if (
            not self.no_expiration
            and self.valid_from
            and self.expiration_date
            and self.expiration_date < self.valid_from
        ):
            raise ValueError("Son geçerlilik tarihi başlangıç tarihinden önce olamaz.")
        if self.document_number:
            self.document_number = assert_meaningful_text(
                self.document_number,
                label="Belge numarası",
                min_len=1,
                required=False,
            )
        if self.issuing_organization:
            self.issuing_organization = assert_meaningful_text(
                self.issuing_organization,
                label="Düzenleyen kurum",
                min_len=2,
                required=False,
            )
        if self.change_reason:
            self.change_reason = assert_meaningful_text(
                self.change_reason,
                label="Değişiklik gerekçesi",
                min_len=3,
                required=False,
            )
        return self


class PersonnelProfileDocumentArchive(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def sanitize_reason(self):
        self.reason = assert_meaningful_text(
            self.reason,
            label="Arşivleme gerekçesi",
            min_len=3,
            required=True,
        )
        return self
