from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.entities import AssignmentStatus, ProfessionalType

class OsgbCreate(BaseModel):
    name: str = Field(min_length=2, max_length=220)
    authorization_number: str | None = None
    tax_number: str | None = None
    responsible_manager: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None


class OsgbUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=220)
    authorization_number: str | None = None
    tax_number: str | None = None
    responsible_manager: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    is_active: bool | None = None


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

class ProfessionalUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = None
    professional_type: ProfessionalType | None = None
    certificate_class: str | None = None
    certificate_number: str | None = None
    certificate_date: date | None = None
    is_active: bool | None = None

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
