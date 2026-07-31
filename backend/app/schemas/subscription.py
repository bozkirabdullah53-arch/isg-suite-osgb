from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.entities import SubscriptionPlan, SubscriptionStatus


class SubscriptionUpdate(BaseModel):
    plan: SubscriptionPlan
    status: SubscriptionStatus
    trial_ends_at: datetime | None = None
    current_period_ends_at: datetime | None = None
    max_users: int = Field(default=3, ge=1, le=10000)
    max_employees: int = Field(default=50, ge=1, le=1000000)
    is_auto_renew: bool = False


class SubscriptionResponse(SubscriptionUpdate):
    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
