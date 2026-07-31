from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ESignRequestCreate(BaseModel):
    company_id: int
    document_id: int | None = None
    document_title: str = Field(min_length=3, max_length=220)
    document_kind: str = Field(default="general", max_length=80)
    document_version: str = Field(default="1", max_length=30)
    document_sha256: str = Field(min_length=64, max_length=64)
    signing_format: str = Field(default="PAdES", pattern="^(PAdES|XAdES|CAdES)$")
    required_signer_name: str = Field(min_length=3, max_length=160)
    required_signer_role: str = Field(min_length=2, max_length=100)
    signing_order: int = Field(default=1, ge=1, le=100)

    @field_validator("document_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        value = value.lower().strip()
        if any(c not in "0123456789abcdef" for c in value):
            raise ValueError("SHA-256 değeri yalnızca hexadecimal karakterlerden oluşmalıdır.")
        return value


class ESignComplete(BaseModel):
    nonce: str = Field(min_length=32, max_length=256)
    document_sha256: str = Field(min_length=64, max_length=64)
    signed_document_sha256: str = Field(min_length=64, max_length=64)
    signature_value: str = Field(min_length=16, max_length=250000)
    certificate_subject: str = Field(min_length=3, max_length=500)
    certificate_serial: str = Field(min_length=1, max_length=160)
    certificate_issuer: str | None = Field(default=None, max_length=500)
    certificate_valid_from: datetime | None = None
    certificate_valid_to: datetime | None = None
    certificate_qualified: bool | None = None
    revocation_status: str | None = Field(default=None, max_length=40)
    timestamp_status: str | None = Field(default=None, max_length=40)


class ESignRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int
    document_id: int | None
    document_title: str
    document_kind: str
    document_version: str
    document_sha256: str
    signing_format: str
    required_signer_name: str
    required_signer_role: str
    signing_order: int
    status: str
    certificate_subject: str | None
    certificate_serial: str | None
    certificate_qualified: bool | None
    revocation_status: str | None
    timestamp_status: str | None
    signed_document_sha256: str | None
    signed_at: datetime | None
    verification_status: str
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
