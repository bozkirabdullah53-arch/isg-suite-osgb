from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.entities import UserRole
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=10, max_length=128)
    role: UserRole
    company_id: int | None = None
class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    role: UserRole | None = None
    company_id: int | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=128)
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    company_id: int | None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
