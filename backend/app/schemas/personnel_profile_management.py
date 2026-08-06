"""Dijital Personel Kartı yönetim işlemleri için dar ve güvenli şemalar."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.input_rules import assert_meaningful_text


class PersonnelProfileEntryArchive(BaseModel):
    """Bir profil girdisini fiziksel silmeden yeni arşiv sürümüyle sonlandırır."""

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


def validate_profile_entry_key(value: str) -> str:
    """URL'den gelen sürüm anahtarını UUID olarak doğrular."""

    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError("Geçersiz profil kayıt anahtarı.") from exc
