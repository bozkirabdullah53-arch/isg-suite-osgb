"""Global-admin-only AI gateway management endpoints."""
from __future__ import annotations

import logging
from time import perf_counter

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import User, UserRole
from app.services.ai_gateway_config import (
    apply_managed_runtime,
    connection_test_payload,
    public_config,
    reset_managed_config,
    restore_legacy_runtime,
    save_managed_config,
)
from app.services.audit import add_audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-settings", tags=["EİSA AI Gateway"])


class AiGatewayUpdate(BaseModel):
    enabled: bool = False
    provider: str = Field(default="heuristic", min_length=2, max_length=40)
    model: str | None = Field(default=None, max_length=160)
    base_url: str | None = Field(default=None, max_length=500)
    timeout_sec: int = Field(default=30, ge=5, le=120)
    api_key: str | None = Field(default=None, max_length=1200)
    clear_api_key: bool = False


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _safe_error(status: int) -> str:
    if status in (401, 403):
        return "Kimlik doğrulama başarısız. API anahtarını ve sağlayıcı hesabını kontrol edin."
    if status == 404:
        return "API adresi veya model bulunamadı. Base URL ve model adını kontrol edin."
    if status == 429:
        return "Sağlayıcı kota/rate limit yanıtı verdi. Hesap bakiyesini ve limitleri kontrol edin."
    if 400 <= status < 500:
        return f"Sağlayıcı isteği reddetti (HTTP {status}). Model ve hesap yetkilerini kontrol edin."
    return f"Sağlayıcı geçici hata verdi (HTTP {status})."


@router.get("")
def get_ai_gateway_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    try:
        config = public_config(db)
        if config.get("managed"):
            apply_managed_runtime(db)
        return config
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("")
def update_ai_gateway_settings(
    payload: AiGatewayUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    before = public_config(db)
    try:
        result = save_managed_config(
            db,
            enabled=payload.enabled,
            provider=payload.provider,
            model=payload.model,
            base_url=payload.base_url,
            timeout_sec=payload.timeout_sec,
            api_key=payload.api_key,
            clear_api_key=payload.clear_api_key,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc

    add_audit_log(
        db,
        user=admin,
        action="ai_gateway_settings_updated",
        module="eisa",
        entity_type="ai_gateway",
        description=(
            "Global AI yönlendirmesi güncellendi: "
            f"provider={result['provider']}, model={result['model'] or '-'}, "
            f"enabled={result['enabled']}"
        ),
        old_value=str({
            "source": before.get("source"),
            "enabled": before.get("enabled"),
            "provider": before.get("provider"),
            "model": before.get("model"),
            "api_key_configured": before.get("api_key_configured"),
        }),
        new_value=str({
            "source": result.get("source"),
            "enabled": result.get("enabled"),
            "provider": result.get("provider"),
            "model": result.get("model"),
            "api_key_configured": result.get("api_key_configured"),
        }),
        ip_address=_client_ip(request),
    )
    db.commit()
    try:
        apply_managed_runtime(db)
    except Exception:
        logger.warning("AI gateway runtime refresh after save failed.", exc_info=True)
    return public_config(db)


@router.post("/test")
def test_ai_gateway_connection(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    try:
        target = connection_test_payload(db)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    if target["local"]:
        label = "YOLO" if target["provider"] == "yolo" else "Heuristik"
        return {
            "ok": True,
            "provider": target["provider"],
            "model": target["model"],
            "latency_ms": 0,
            "message": f"{label} yerel mod seçili; dış API bağlantısı gerekmiyor.",
        }

    started = perf_counter()
    try:
        with httpx.Client(timeout=float(target["timeout_sec"])) as client:
            response = client.post(
                f"{str(target['base_url']).rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {target['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": target["model"],
                    "messages": [
                        {
                            "role": "user",
                            "content": "Return exactly OK. This is an API connectivity check.",
                        }
                    ],
                    "max_tokens": 8,
                    "temperature": 0,
                },
            )
        latency_ms = int((perf_counter() - started) * 1000)
        if not response.is_success:
            raise HTTPException(response.status_code, _safe_error(response.status_code))
        data = response.json()
        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices:
            raise HTTPException(502, "Sağlayıcı beklenen Chat Completions yanıtını vermedi.")
        return {
            "ok": True,
            "provider": target["provider"],
            "model": target["model"],
            "latency_ms": latency_ms,
            "message": "API bağlantısı ve model erişimi başarılı.",
        }
    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "AI sağlayıcısı bağlantı testi zaman aşımına uğradı.") from exc
    except httpx.RequestError as exc:
        logger.warning("AI gateway connection test network error: %s", type(exc).__name__)
        raise HTTPException(502, "AI sağlayıcısına ağ bağlantısı kurulamadı.") from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(502, "AI sağlayıcısının yanıtı beklenen formatta değil.") from exc


@router.post("/reset")
def reset_ai_gateway_settings(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    before = public_config(db)
    reset_managed_config(db)
    add_audit_log(
        db,
        user=admin,
        action="ai_gateway_settings_reset",
        module="eisa",
        entity_type="ai_gateway",
        description="Global AI panel ayarları kaldırıldı; environment ayarlarına dönüldü.",
        old_value=str({
            "enabled": before.get("enabled"),
            "provider": before.get("provider"),
            "model": before.get("model"),
            "api_key_configured": before.get("api_key_configured"),
        }),
        new_value="{'source': 'environment'}",
        ip_address=_client_ip(request),
    )
    db.commit()
    restore_legacy_runtime()
    return public_config(db)
