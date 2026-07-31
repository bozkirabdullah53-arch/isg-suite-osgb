from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.entities import DocumentCategory


class DocumentCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    category: DocumentCategory
    title: str = Field(min_length=3, max_length=220)
    file_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1500)
    valid_from: date | None = None
    valid_until: date | None = None
    version: str | None = Field(default=None, max_length=30)


class DocumentResponse(DocumentCreate):
    id: int
    is_active: bool
    created_by_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
