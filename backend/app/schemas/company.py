from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    sgk_registry_no: str = Field(min_length=1, max_length=40)
    tax_number: str | None = None
    nace_code: str | None = None
    hazard_class: str | None = None
    osgb_id: int | None = None

    @field_validator("sgk_registry_no")
    @classmethod
    def strip_sgk(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("İşyeri sicil numarası zorunludur.")
        return s


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    tax_number: str | None = None
    nace_code: str | None = None
    hazard_class: str | None = None
    sgk_registry_no: str | None = Field(default=None, min_length=1, max_length=40)
    is_active: bool | None = None
    osgb_id: int | None = None

    @field_validator("sgk_registry_no")
    @classmethod
    def strip_sgk_opt(cls, v: str | None) -> str | None:
        if v is None:
            return v
        s = v.strip()
        if not s:
            raise ValueError("İşyeri sicil numarası boş olamaz.")
        return s


class CompanyResponse(BaseModel):
    id: int
    name: str
    tax_number: str | None = None
    nace_code: str | None = None
    hazard_class: str | None = None
    sgk_registry_no: str | None = None
    is_active: bool
    osgb_id: int | None = None
    model_config = ConfigDict(from_attributes=True)
