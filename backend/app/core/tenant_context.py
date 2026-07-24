"""TenantContext — istek bazlı OSGB/firma kapsamı (P1-03 scaffold).

Mevcut company_access / ensure_* yardımcıları korunur; yeni kod buradan okuyabilir.
Global admin için osgb_id None olabilir (platform geneli).
"""
from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

from fastapi import HTTPException

from app.models.entities import User, UserRole

_tenant_ctx: ContextVar["TenantContext | None"] = ContextVar("tenant_context", default=None)


@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: int
    role: UserRole
    osgb_id: int | None
    company_id: int | None

    @property
    def is_global(self) -> bool:
        return self.role == UserRole.GLOBAL_ADMIN

    @property
    def has_osgb(self) -> bool:
        return self.osgb_id is not None


def tenant_from_user(user: User) -> TenantContext:
    return TenantContext(
        user_id=int(user.id),
        role=user.role,
        osgb_id=int(user.osgb_id) if user.osgb_id else None,
        company_id=int(user.company_id) if user.company_id else None,
    )


def set_tenant(ctx: TenantContext | None) -> Token:
    return _tenant_ctx.set(ctx)


def reset_tenant(token: Token) -> None:
    _tenant_ctx.reset(token)


def clear_tenant() -> None:
    _tenant_ctx.set(None)


def current_tenant() -> TenantContext | None:
    return _tenant_ctx.get()


def require_tenant() -> TenantContext:
    ctx = current_tenant()
    if ctx is None:
        raise HTTPException(401, "Oturum kapsamı bulunamadı.")
    return ctx


def require_osgb_id() -> int:
    """OSGB zorunlu roller için; global admin'de 400 (bilinçli seçim gerekir)."""
    ctx = require_tenant()
    if ctx.is_global:
        raise HTTPException(400, "Bu işlem için OSGB seçimi gerekir.")
    if not ctx.osgb_id:
        raise HTTPException(403, "OSGB kapsamınız tanımlı değil.")
    return ctx.osgb_id


def assert_osgb_access(osgb_id: int | None) -> None:
    """Kayıt osgb_id'si kullanıcının kapsamına uyuyor mu? Global admin geçer."""
    if osgb_id is None:
        raise HTTPException(404, "Kayıt bulunamadı.")
    ctx = require_tenant()
    if ctx.is_global:
        return
    if not ctx.osgb_id or int(osgb_id) != int(ctx.osgb_id):
        raise HTTPException(403, "Bu OSGB kapsamına erişiminiz yok.")


def bind_user_tenant(user: User) -> TenantContext:
    """Auth sonrası çağrılır — ContextVar'a yazar."""
    ctx = tenant_from_user(user)
    set_tenant(ctx)
    return ctx
