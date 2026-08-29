from __future__ import annotations
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractorWorkerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=160)
    national_id_masked: str | None = Field(default=None, max_length=20)
    job_title: str | None = Field(default=None, max_length=120)


class ContractorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=220)
    contract_number: str | None = Field(default=None, max_length=120)
    contract_start: date | None = None
    contract_end: date | None = None
    contact_name: str | None = Field(default=None, max_length=160)
    contact_phone: str | None = Field(default=None, max_length=40)
    workers: list[ContractorWorkerInput] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.contract_start and self.contract_end and self.contract_end < self.contract_start:
            raise ValueError("Sözleşme bitişi başlangıçtan önce olamaz.")
        self.name = self.name.strip()
        return self


class ContractorDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_type: str = Field(min_length=2, max_length=60)
    title: str = Field(min_length=2, max_length=220)
    file_name: str | None = Field(default=None, max_length=255)
    valid_until: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
