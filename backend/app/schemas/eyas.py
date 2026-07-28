"""Eyas Digital Approval şemaları — nitelikli e-imza değildir."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EyasStepIn(BaseModel):
    assignee_user_id: int
    role_label: str = Field(min_length=2, max_length=100)
    step_order: int | None = Field(default=None, ge=1, le=100)


class EyasWorkflowCreate(BaseModel):
    company_id: int
    title: str = Field(min_length=2, max_length=220)
    document_kind: str = Field(default="genel", max_length=80)
    source_document_id: int | None = None
    source_sha256: str | None = Field(default=None, max_length=64)
    steps: list[EyasStepIn] = Field(min_length=1, max_length=20)


class EyasStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workflow_id: int
    company_id: int
    step_order: int
    assignee_user_id: int
    assignee_name: str | None = None
    role_label: str
    status: str
    decided_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    device_note: str | None = None
    note: str | None = None
    created_at: datetime


class EyasWorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int
    title: str
    document_kind: str
    source_document_id: int | None = None
    source_sha256: str | None = None
    status: str
    current_step_order: int
    legal_label: str
    qes_request_id: int | None = None
    archive_path: str | None = None
    locked_at: datetime | None = None
    created_by_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    steps: list[EyasStepOut] = []


class EyasDecideBody(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
    device_note: str | None = Field(default=None, max_length=240)


class EyasEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workflow_id: int
    step_id: int | None
    action: str
    actor_user_id: int | None
    prev_hash: str | None
    event_hash: str
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class EyasMetaOut(BaseModel):
    enabled: bool
    product: str = "Eyas Digital Approval"
    legal_label: str = "digital_approval_not_qes"
    notice: str = (
        "Bu süreç Dijital Onaydır; nitelikli elektronik imza (5070) değildir. "
        "Her kullanıcı yalnızca kendi hesabı ile onaylar."
    )
    qes_extension_point: str = "/api/v1/esign"
