from pydantic import BaseModel, ConfigDict, Field
class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    tax_number: str | None = None
    nace_code: str | None = None
    hazard_class: str | None = None
class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    tax_number: str | None = None
    nace_code: str | None = None
    hazard_class: str | None = None
    is_active: bool | None = None
class CompanyResponse(CompanyCreate):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
