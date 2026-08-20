"""API contracts for the isolated Basic Occupational Health and Safety course."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.remote_training import REMOTE_TRAINING_TYPE


class RemoteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RemoteProgramCreate(RemoteModel):
    company_id: int = Field(gt=0)
    branch_id: int | None = Field(default=None, gt=0)
    title: str = Field(default=REMOTE_TRAINING_TYPE, min_length=3, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    learning_objectives: str | None = Field(default=None, max_length=5000)
    instructor_name: str | None = Field(default=None, max_length=180)
    instructor_qualification: str | None = Field(default=None, max_length=220)
    completion_threshold_percent: int = Field(default=90, ge=1, le=100)
    passing_score: int = Field(default=60, ge=0, le=100)
    attempt_limit: int = Field(default=3, ge=1, le=10)
    requires_final_exam: bool = True


class RemoteProgramUpdate(RemoteModel):
    title: str | None = Field(default=None, min_length=3, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    learning_objectives: str | None = Field(default=None, max_length=5000)
    instructor_name: str | None = Field(default=None, max_length=180)
    instructor_qualification: str | None = Field(default=None, max_length=220)
    completion_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    passing_score: int | None = Field(default=None, ge=0, le=100)
    attempt_limit: int | None = Field(default=None, ge=1, le=10)
    requires_final_exam: bool | None = None
    branch_id: int | None = Field(default=None, gt=0)


class RemoteSectionCreate(RemoteModel):
    sector_code: str = Field(default="common", min_length=2, max_length=64)
    title: str = Field(min_length=2, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    learning_objectives: str | None = Field(default=None, max_length=5000)
    order_index: int | None = Field(default=None, ge=1)
    is_required: bool = True


class RemoteSectionUpdate(RemoteModel):
    sector_code: str | None = Field(default=None, min_length=2, max_length=64)
    title: str | None = Field(default=None, min_length=2, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    learning_objectives: str | None = Field(default=None, max_length=5000)
    order_index: int | None = Field(default=None, ge=1)
    is_required: bool | None = None


class RemoteVideoUpdate(RemoteModel):
    title: str | None = Field(default=None, min_length=2, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    learning_objectives: str | None = Field(default=None, max_length=5000)
    order_index: int | None = Field(default=None, ge=1)
    is_required: bool | None = None


class RemoteCatalogSectionCreate(RemoteModel):
    code: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=2, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    order_index: int | None = Field(default=None, ge=1)
    is_required: bool = True


class RemoteCatalogSectionUpdate(RemoteModel):
    code: str | None = Field(default=None, min_length=2, max_length=64)
    title: str | None = Field(default=None, min_length=2, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    order_index: int | None = Field(default=None, ge=1)
    is_required: bool | None = None


class RemoteCatalogMaterialize(RemoteModel):
    """Create an immutable company program from a published catalog package."""

    company_id: int = Field(gt=0)
    branch_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=3, max_length=220)
    instructor_name: str | None = Field(default=None, max_length=180)
    instructor_qualification: str | None = Field(default=None, max_length=220)


class RemoteAssignmentCreate(RemoteModel):
    employee_ids: list[int] = Field(min_length=1, max_length=2000)
    branch_id: int | None = Field(default=None, gt=0)
    due_date: date | None = None

    @field_validator("employee_ids")
    @classmethod
    def unique_positive_ids(cls, value: list[int]) -> list[int]:
        normalized = sorted({int(item) for item in value if int(item) > 0})
        if not normalized:
            raise ValueError("En az bir aktif çalışan seçilmelidir.")
        return normalized


class RemoteProgressCreate(RemoteModel):
    position_seconds: float = Field(default=0, ge=0)
    event_type: Literal["start", "resume", "progress", "pause", "ended"] = "progress"
    device_info: str | None = Field(default=None, max_length=500)


class RemoteCheckpointQuestionCreate(RemoteModel):
    sector_code: str | None = Field(default=None, min_length=2, max_length=64)
    question_text: str = Field(min_length=3, max_length=3000)
    options: dict[str, str]
    correct_option: str = Field(pattern=r"^[A-Da-d]$")
    explanation: str | None = Field(default=None, max_length=3000)
    timestamp_seconds: int | None = Field(default=None, ge=0)
    order_index: int = Field(default=1, ge=1)
    is_required: bool = False
    section_id: int | None = Field(default=None, gt=0)
    video_id: int | None = Field(default=None, gt=0)

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: dict[str, str]) -> dict[str, str]:
        clean = {str(key).upper(): str(text).strip() for key, text in value.items()}
        if set(clean) != {"A", "B", "C", "D"} or any(not text for text in clean.values()):
            raise ValueError("Soru seçenekleri tam olarak A, B, C ve D olmalıdır.")
        return clean

    @field_validator("correct_option")
    @classmethod
    def normalize_correct_option(cls, value: str) -> str:
        return value.upper()


class RemoteFinalExamQuestionUpdate(RemoteModel):
    """Edit one catalog-derived final question before program publication."""

    question_text: str = Field(min_length=3, max_length=3000)
    options: dict[str, str]
    correct_option: str = Field(pattern=r"^[A-Da-d]$")
    explanation: str | None = Field(default=None, max_length=3000)

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: dict[str, str]) -> dict[str, str]:
        clean = {str(key).upper(): str(text).strip() for key, text in value.items()}
        if set(clean) != {"A", "B", "C", "D"} or any(not text for text in clean.values()):
            raise ValueError("Soru seçenekleri tam olarak A, B, C ve D olmalıdır.")
        if len({text.casefold() for text in clean.values()}) != 4:
            raise ValueError("Soru seçenekleri birbirinden farklı olmalıdır.")
        return clean

    @field_validator("correct_option")
    @classmethod
    def normalize_correct_option(cls, value: str) -> str:
        return value.upper()


class RemoteProgramQuestionLink(RemoteModel):
    question_id: int = Field(gt=0)
    position: int = Field(default=1, ge=1)
    sector_code: str | None = Field(default=None, min_length=2, max_length=64)


class RemoteProgramSectorUpdate(RemoteModel):
    sector_codes: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("sector_codes")
    @classmethod
    def normalize_sector_codes(cls, value: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for item in value:
            code = str(item).strip().lower()
            if code and code not in seen:
                normalized.append(code)
                seen.add(code)
        return normalized


class RemoteExamSubmit(RemoteModel):
    answers: dict[str, str]

    @field_validator("answers")
    @classmethod
    def normalize_answers(cls, value: dict[str, str]) -> dict[str, str]:
        return {str(key): str(answer).strip().upper() for key, answer in value.items()}


class RemoteEmployeeAccessCreate(RemoteModel):
    company_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)


class RemoteEmployeeAccountProvision(RemoteModel):
    company_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)
    # Eski istemcilerden gelen alanı kabul ederiz; yeni akış bu alanı
    # kullanmaz ve kullanıcı adını çalışanın ad-soyadından üretir.
    email: EmailStr | None = None


JsonObject = dict[str, Any]
