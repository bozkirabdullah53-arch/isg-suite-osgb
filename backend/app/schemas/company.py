from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.input_rules import assert_meaningful_text, assert_person_name, clean_text


class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    sgk_registry_no: str = Field(min_length=1, max_length=40)
    hazard_class: str | None = None
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=40)
    authorized_person: str | None = Field(default=None, max_length=160)
    osgb_id: int | None = None
    # Legacy alanlar — istemci göndermese de API uyumluluğu için opsiyonel
    tax_number: str | None = None
    nace_code: str | None = None

    @field_validator("sgk_registry_no")
    @classmethod
    def strip_sgk(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("İşyeri sicil numarası zorunludur.")
        if len(s) < 3:
            raise ValueError("İşyeri sicil numarası en az 3 karakter olmalıdır.")
        return s

    @model_validator(mode="after")
    def sanitize(self):
        self.name = assert_meaningful_text(self.name, label="İşyeri adı", min_len=2, required=True)
        self.address = assert_meaningful_text(self.address, label="Adres", min_len=5, required=False)
        self.authorized_person = assert_person_name(self.authorized_person, label="Yetkili kişi")
        self.phone = clean_text(self.phone)
        if self.phone and len(self.phone) < 7:
            raise ValueError("Telefon en az 7 karakter olmalıdır.")
        return self


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    hazard_class: str | None = None
    sgk_registry_no: str | None = Field(default=None, min_length=1, max_length=40)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=40)
    authorized_person: str | None = Field(default=None, max_length=160)
    is_active: bool | None = None
    osgb_id: int | None = None
    tax_number: str | None = None
    nace_code: str | None = None

    @field_validator("sgk_registry_no")
    @classmethod
    def strip_sgk_opt(cls, v: str | None) -> str | None:
        if v is None:
            return v
        s = v.strip()
        if not s:
            raise ValueError("İşyeri sicil numarası boş olamaz.")
        if len(s) < 3:
            raise ValueError("İşyeri sicil numarası en az 3 karakter olmalıdır.")
        return s

    @model_validator(mode="after")
    def sanitize(self):
        if self.name is not None:
            self.name = assert_meaningful_text(self.name, label="İşyeri adı", min_len=2, required=True)
        if self.address is not None:
            self.address = assert_meaningful_text(self.address, label="Adres", min_len=5, required=False)
        if self.authorized_person is not None:
            self.authorized_person = assert_person_name(self.authorized_person, label="Yetkili kişi")
        if self.phone is not None:
            self.phone = clean_text(self.phone)
            if self.phone and len(self.phone) < 7:
                raise ValueError("Telefon en az 7 karakter olmalıdır.")
        return self


class CompanyResponse(BaseModel):
    id: int
    name: str
    hazard_class: str | None = None
    sgk_registry_no: str | None = None
    address: str | None = None
    phone: str | None = None
    authorized_person: str | None = None
    is_active: bool
    osgb_id: int | None = None
    model_config = ConfigDict(from_attributes=True)
