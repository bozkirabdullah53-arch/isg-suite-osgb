from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=10, max_length=128)


class TokenResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_setup_required: bool = False
    mfa_token: str | None = None
    refresh_cookie: bool = False
    # P1-01: saniye; refresh cookie açıkken kısa access süresi
    expires_in: int | None = None


class CurrentUserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    company_id: int | None
    osgb_id: int | None = None
    is_eisa: bool = False
    subscription_write_allowed: bool = True
    subscription_status: str | None = None
    mfa_enabled: bool = False
    mfa_required: bool = False
