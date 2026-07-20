from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.input_rules import assert_event_date, assert_meaningful_text, assert_person_name, clean_text
from app.models.entities import AssignmentStatus, ProfessionalType


class OsgbCreate(BaseModel):
    name: str = Field(min_length=2, max_length=220)
    authorization_number: str | None = None
    tax_number: str | None = None
    responsible_manager: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None

    @model_validator(mode="after")
    def sanitize(self):
        self.name = assert_meaningful_text(self.name, label="OSGB unvanı", min_len=2, required=True)
        self.responsible_manager = assert_person_name(self.responsible_manager, label="Sorumlu müdür")
        self.address = assert_meaningful_text(self.address, label="Adres", min_len=5, required=False)
        self.phone = clean_text(self.phone)
        self.authorization_number = clean_text(self.authorization_number)
        self.tax_number = clean_text(self.tax_number)
        return self


class OsgbUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=220)
    authorization_number: str | None = None
    tax_number: str | None = None
    responsible_manager: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def sanitize(self):
        if self.name is not None:
            self.name = assert_meaningful_text(self.name, label="OSGB unvanı", min_len=2, required=True)
        if self.responsible_manager is not None:
            self.responsible_manager = assert_person_name(self.responsible_manager, label="Sorumlu müdür")
        if self.address is not None:
            self.address = assert_meaningful_text(self.address, label="Adres", min_len=5, required=False)
        if self.phone is not None:
            self.phone = clean_text(self.phone)
        if self.authorization_number is not None:
            self.authorization_number = clean_text(self.authorization_number)
        if self.tax_number is not None:
            self.tax_number = clean_text(self.tax_number)
        return self


class OsgbResponse(OsgbCreate):
    id: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProfessionalCreate(BaseModel):
    osgb_id: int
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str | None = None
    professional_type: ProfessionalType
    certificate_class: str | None = None
    certificate_number: str | None = None
    certificate_date: date | None = None

    @model_validator(mode="after")
    def sanitize(self):
        self.full_name = assert_person_name(self.full_name, label="Ad soyad", required=True)
        self.phone = clean_text(self.phone)
        self.certificate_number = clean_text(self.certificate_number)
        self.certificate_class = clean_text(self.certificate_class)
        self.certificate_date = assert_event_date(
            self.certificate_date, label="Belge tarihi", required=False, allow_future_days=0
        )
        return self


class ProfessionalUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = None
    professional_type: ProfessionalType | None = None
    certificate_class: str | None = None
    certificate_number: str | None = None
    certificate_date: date | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def sanitize(self):
        if self.full_name is not None:
            self.full_name = assert_person_name(self.full_name, label="Ad soyad", required=True)
        if self.phone is not None:
            self.phone = clean_text(self.phone)
        if self.certificate_number is not None:
            self.certificate_number = clean_text(self.certificate_number)
        if self.certificate_class is not None:
            self.certificate_class = clean_text(self.certificate_class)
        if self.certificate_date is not None:
            self.certificate_date = assert_event_date(
                self.certificate_date, label="Belge tarihi", required=False, allow_future_days=0
            )
        return self

class ProfessionalResponse(BaseModel):
    id: int
    osgb_id: int
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    professional_type: ProfessionalType
    certificate_class: str | None = None
    certificate_number: str | None = None
    certificate_date: date | None = None
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProfessionalLoginAccount(BaseModel):
    user_id: int
    email: str
    full_name: str
    temporary_password: str
    created: bool
    message: str = "Geçici giriş şifresi oluşturuldu. Profesyonel Güvenlik menüsünden değiştirebilir."


class ProfessionalCreateResponse(ProfessionalResponse):
    login_account: ProfessionalLoginAccount | None = None

class AssignmentCreate(BaseModel):
    osgb_id: int
    company_id: int
    professional_id: int
    professional_type: ProfessionalType
    start_date: date
    end_date: date | None = None
    required_minutes_monthly: int = 0
    planned_minutes_monthly: int = 0
    actual_minutes_monthly: int = 0
    isg_katip_contract_number: str | None = None

class AssignmentResponse(AssignmentCreate):
    id: int
    status: AssignmentStatus
    created_at: datetime
    contract_file_name: str | None = None
    contract_content_type: str | None = None
    model_config = ConfigDict(from_attributes=True)

class ContractCreate(BaseModel):
    osgb_id: int
    company_id: int
    contract_number: str
    start_date: date
    end_date: date | None = None
    monthly_fee: int | None = None

class ContractResponse(ContractCreate):
    id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
