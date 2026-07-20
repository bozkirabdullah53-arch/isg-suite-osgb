from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.validators import parse_optional_datetime


class EisaPackageCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    price_monthly: Decimal = Field(default=Decimal("0"), ge=0)
    price_yearly: Decimal = Field(default=Decimal("0"), ge=0)
    max_users: int = Field(default=50, ge=1, le=10000)
    max_workplaces: int = Field(default=100, ge=1, le=100000)
    is_active: bool = True
    sort_order: int = 0


class EisaPackageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    price_monthly: Decimal | None = Field(default=None, ge=0)
    price_yearly: Decimal | None = Field(default=None, ge=0)
    max_users: int | None = Field(default=None, ge=1, le=10000)
    max_workplaces: int | None = Field(default=None, ge=1, le=100000)
    is_active: bool | None = None
    sort_order: int | None = None


class EisaPackageResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    price_monthly: Decimal
    price_yearly: Decimal
    max_users: int
    max_workplaces: int
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EisaPaymentCreate(BaseModel):
    osgb_id: int
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="TRY", max_length=8)
    payment_method: str | None = None
    payment_status: str = "completed"
    payment_date: datetime | None = None
    description: str | None = Field(default=None, max_length=1000)
    period_start: datetime | None = None
    period_end: datetime | None = None
    reference_no: str | None = Field(default=None, max_length=80)

    @field_validator("payment_date", "period_start", "period_end", mode="before")
    @classmethod
    def _parse_dates(cls, value):
        if value is None or value == "":
            return None
        return parse_optional_datetime(value)


class EisaPaymentResponse(BaseModel):
    id: int
    reference_no: str
    osgb_id: int
    osgb_name: str | None = None
    subscription_id: int | None
    amount: Decimal
    currency: str
    payment_method: str | None
    payment_status: str
    payment_date: datetime
    description: str | None
    period_start: datetime | None
    period_end: datetime | None
    recorded_by_user_id: int | None
    recorded_by_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EisaNotificationCreate(BaseModel):
    channel: str = "in_app"
    target_scope: str = "all_osgb"
    target_osgb_id: int | None = None
    title: str = Field(min_length=2, max_length=220)
    message: str = Field(min_length=2, max_length=2000)


class EisaNotificationResponse(BaseModel):
    id: int
    channel: str
    target_scope: str
    target_osgb_id: int | None
    target_osgb_name: str | None = None
    title: str
    message: str
    status: str
    sent_at: datetime | None
    created_by_user_id: int | None
    created_by_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EisaAuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    user_name: str | None = None
    action: str
    module: str | None
    entity_type: str
    entity_id: str | None
    description: str | None
    old_value: str | None
    new_value: str | None
    ip_address: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EisaOsgbUserResponse(BaseModel):
    id: int
    name: str
    authorization_number: str | None
    tax_number: str | None
    responsible_manager: str | None
    contact_email: str | None
    contact_phone: str | None
    is_active: bool
    archived_at: datetime | None
    subscription_status: str | None = None
    effective_status: str | None = None
    package_name: str | None = None
    trial_ends_at: datetime | None = None
    current_period_ends_at: datetime | None = None
    write_allowed: bool = False
    created_at: datetime


class EisaSettingsUpdate(BaseModel):
    trial_days: int | None = Field(default=None, ge=1, le=90)
    expiring_window_days: int | None = Field(default=None, ge=1, le=90)
    support_email: str | None = Field(default=None, max_length=255)
    support_phone: str | None = Field(default=None, max_length=40)
