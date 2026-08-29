from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    # Eski istemciler alanı "email" adıyla göndermeye devam eder; değer artık
    # e-posta adresi veya kullanıcı adı olabilir (ör. A.bozkir).
    email: str = Field(min_length=1, max_length=255)
    password: str


class RegisterRequest(BaseModel):
    """Bireysel İSG uzmanı mobil kayıt formu."""

    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    password_confirm: str = Field(min_length=10, max_length=128)
    phone: str | None = Field(default=None, max_length=40)
    certificate_class: Literal["A", "B", "C"]
    certificate_number: str = Field(min_length=3, max_length=80)
    contract_accepted: bool
    personal_data_accepted: bool


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class MfaRestartSetupRequest(BaseModel):
    """Authenticator yoksa: şifre doğrulanır, MFA sıfırlanır, kurulum token’ı verilir."""

    # Eski istemciler alanı "email" adıyla gönderir; değer e-posta veya
    # kullanıcı adı olabilir.
    email: str = Field(min_length=1, max_length=255)
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=10, max_length=128)
    # Optional for backward compatibility with existing API clients; new UI
    # sends it so a mistyped password cannot lock the employee out again.
    new_password_confirm: str | None = Field(default=None, min_length=10, max_length=128)


class TokenResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_setup_required: bool = False
    password_change_required: bool = False
    mfa_setup_deferred: bool = False
    mfa_token: str | None = None
    refresh_cookie: bool = False
    # P1-01: saniye; refresh cookie açıkken kısa access süresi
    expires_in: int | None = None


class CurrentUserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str | None = None
    full_name: str
    role: str
    company_id: int | None
    osgb_id: int | None = None
    is_individual: bool = False
    is_eisa: bool = False
    subscription_write_allowed: bool = True
    subscription_status: str | None = None
    mfa_enabled: bool = False
    mfa_required: bool = False
    password_change_required: bool = False
