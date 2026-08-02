from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class QuestionScopeInput(BaseModel):
    type: Literal["common", "hazard", "sector", "nace"]
    value: str = Field(default="*", min_length=1, max_length=140)


class QuestionSourceInput(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    url: HttpUrl
    reference: str = Field(min_length=2, max_length=300)
    effective_date: date | None = None


class QuestionCreate(BaseModel):
    question_code: str = Field(min_length=3, max_length=60, pattern=r"^[A-Za-z0-9_.-]+$")
    version: int = Field(default=1, ge=1)
    topic_code: str = Field(min_length=2, max_length=100)
    topic_label: str = Field(min_length=3, max_length=300)
    question_text: str = Field(min_length=12, max_length=2000)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: Literal["A", "B", "C", "D"]
    answer_explanation: str = Field(min_length=12, max_length=4000)
    scopes: list[QuestionScopeInput] = Field(min_length=1)
    sources: list[QuestionSourceInput] = Field(min_length=1)

    @field_validator("options")
    @classmethod
    def options_valid(cls, values: list[str]) -> list[str]:
        cleaned = [str(value or "").strip() for value in values]
        if any(len(value) < 2 for value in cleaned):
            raise ValueError("Dört seçeneğin tamamı anlamlı biçimde doldurulmalıdır.")
        if len({value.casefold() for value in cleaned}) != 4:
            raise ValueError("Seçenekler birbirinden farklı olmalıdır.")
        return cleaned

    @model_validator(mode="after")
    def scope_values_valid(self):
        for scope in self.scopes:
            if scope.type == "common" and scope.value != "*":
                raise ValueError("Ortak soru kapsamının değeri * olmalıdır.")
            if scope.type != "common" and scope.value == "*":
                raise ValueError(f"{scope.type} kapsamı için gerçek bir değer seçilmelidir.")
        return self


class QuestionUpdate(BaseModel):
    topic_code: str | None = Field(default=None, min_length=2, max_length=100)
    topic_label: str | None = Field(default=None, min_length=3, max_length=300)
    question_text: str | None = Field(default=None, min_length=12, max_length=2000)
    options: list[str] | None = Field(default=None, min_length=4, max_length=4)
    correct_option: Literal["A", "B", "C", "D"] | None = None
    answer_explanation: str | None = Field(default=None, min_length=12, max_length=4000)
    reviewer_note: str | None = Field(default=None, max_length=4000)
    scopes: list[QuestionScopeInput] | None = None
    sources: list[QuestionSourceInput] | None = None

    @field_validator("options")
    @classmethod
    def options_valid(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return QuestionCreate.options_valid(values)


class QuestionResponse(BaseModel):
    id: int
    question_code: str
    version: int
    status: str
    topic_code: str
    topic_label: str
    question_text: str
    options: dict[str, str]
    correct_option: str
    answer_explanation: str
    reviewer_note: str | None
    scopes: list[dict]
    sources: list[dict]
    created_by_id: int
    reviewed_by_id: int | None
    reviewed_at: datetime | None
    published_at: datetime | None
    retired_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExamSnapshotItemResponse(BaseModel):
    position: int
    question_code: str
    question_version: int
    topic_code: str
    topic_label: str
    question_text: str
    options: dict[str, str]
    correct_option: str
    answer_explanation: str
    sources: list[dict]


class ExamSnapshotResponse(BaseModel):
    id: int
    training_id: int
    version: int
    question_count: int
    content_hash: str
    selection_policy: str
    created_at: datetime
    items: list[ExamSnapshotItemResponse]
