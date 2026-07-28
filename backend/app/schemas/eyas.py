"""Eyas Digital Approval şemaları — nitelikli e-imza değildir."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EyasStepIn(BaseModel):
    assignee_user_id: int
    role_label: str = Field(min_length=2, max_length=100)
    step_order: int | None = Field(default=None, ge=1, le=100)


class EyasWorkflowCreate(BaseModel):
    company_id: int
    title: str | None = Field(default=None, max_length=220)
    document_kind: str | None = Field(default=None, max_length=80)
    source_key: str | None = Field(default=None, max_length=160)
    source_document_id: int | None = None
    source_sha256: str | None = Field(default=None, max_length=64)
    steps: list[EyasStepIn] | None = Field(default=None, max_length=20)
    auto_assignees: bool = True


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
    source_key: str | None = None
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
    document_download_path: str | None = None


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
        "Sıra: İş Güvenliği Uzmanı → İşyeri Hekimi → İşveren / vekili. "
        "Her kullanıcı yalnızca kendi hesabı ile onaylar."
    )
    qes_extension_point: str = "/api/v1/esign"
    chain: list[str] = [
        "İş Güvenliği Uzmanı",
        "İşyeri Hekimi",
        "İşveren / vekili",
    ]


class EyasDocItemOut(BaseModel):
    kind: str
    kind_label: str
    source_key: str
    title: str
    source_id: int | None = None
    document_record_id: int | None = None
    readiness: str
    readiness_detail: str
    download_path: str | None = None
    selectable: bool = False


class EyasDocsOut(BaseModel):
    company_id: int
    company_name: str | None = None
    generated_at: str | None = None
    items: list[EyasDocItemOut] = []
    summary: dict[str, Any] = {}


class EyasAssigneeAltOut(BaseModel):
    user_id: int
    full_name: str
    role: str
    mfa_enabled: bool = False


class EyasAssigneeStepOut(BaseModel):
    step_order: int
    role_key: str
    role_label: str
    suggested_user_id: int | None = None
    suggested_user_name: str | None = None
    suggested_source: str | None = None
    alternatives: list[EyasAssigneeAltOut] = []
    warnings: list[str] = []


class EyasAssigneesOut(BaseModel):
    company_id: int
    company_name: str | None = None
    authorized_person_text: str | None = None
    legal_notice: str
    steps: list[EyasAssigneeStepOut] = []
    team: dict[str, Any] = {}
