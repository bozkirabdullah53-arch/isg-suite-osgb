from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.validators import parse_optional_datetime


class OsgbApplicationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=220)
    authorization_number: str = Field(min_length=3, max_length=80)
    tax_number: str = Field(min_length=8, max_length=20)
    responsible_manager: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=500)
    applicant_name: str = Field(min_length=2, max_length=160)
    applicant_email: EmailStr
    notes: str | None = Field(default=None, max_length=2000)
    contract_accepted: bool
    personal_data_accepted: bool


class OsgbApplicationResponse(BaseModel):
    id: int
    name: str
    authorization_number: str
    tax_number: str
    responsible_manager: str | None
    contact_email: str
    contact_phone: str | None
    address: str | None
    applicant_name: str
    applicant_email: str
    notes: str | None
    status: str
    matched_osgb_id: int | None
    auto_matched: bool
    rejection_reason: str | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class OsgbApplicationReject(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class OsgbSubscriptionResponse(BaseModel):
    id: int
    osgb_id: int
    osgb_name: str | None = None
    responsible_manager: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    package_id: int | None = None
    package_name: str | None = None
    plan: str
    status: str
    effective_status: str
    write_allowed: bool
    days_remaining: int | None = None
    trial_ends_at: datetime | None
    current_period_ends_at: datetime | None
    max_users: int
    max_workplaces: int
    last_payment_channel: str | None
    last_payment_date: datetime | None = None
    last_payment_amount: float | None = None
    payment_status: str | None = None
    payment_notes: str | None
    is_auto_renew: bool
    account_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OsgbSubscriptionUpdate(BaseModel):
    status: str | None = None
    package_id: int | None = None
    trial_ends_at: datetime | None = None
    current_period_ends_at: datetime | None = None
    max_users: int | None = Field(default=None, ge=1, le=10000)
    max_workplaces: int | None = Field(default=None, ge=1, le=100000)
    last_payment_channel: str | None = None
    payment_notes: str | None = Field(default=None, max_length=1000)
    is_auto_renew: bool | None = None

    @field_validator("trial_ends_at", "current_period_ends_at", mode="before")
    @classmethod
    def _parse_dates(cls, value):
        if value is None or value == "":
            return None
        return parse_optional_datetime(value)
