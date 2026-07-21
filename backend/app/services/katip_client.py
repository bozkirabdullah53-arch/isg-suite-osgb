"""0.9.125 — İSG-KATİP API adapter scaffold (stub).

Gerçek resmi KATİP sözleşmesi / kimlik bilgisi yokken yalnızca yapılandırma
doğrulama ve stub export payload üretir. Secrets asla loglanmaz / dönülmez.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from app.core.config import settings

ADAPTER_VERSION = "stub-clients-v1"
StatusKind = Literal["configured", "missing_credentials", "stub"]

_last_stub_export_at: str | None = None


def validate_config() -> dict[str, Any]:
    url = (settings.katip_api_url or "").strip()
    key = (settings.katip_api_key or "").strip()
    has_url = bool(url)
    has_key = bool(key)
    configured = has_url and has_key
    return {
        "adapter": "katip",
        "has_url": has_url,
        "has_key": has_key,
        "configured": configured,
        "adapter_version": ADAPTER_VERSION,
    }


def status() -> StatusKind:
    cfg = validate_config()
    if cfg["configured"]:
        return "configured"
    if cfg["has_url"] or cfg["has_key"]:
        return "missing_credentials"
    return "stub"


def last_stub_export_at() -> str | None:
    return _last_stub_export_at


def export_payload(*, osgb_id: int | None = None, dry_run: bool = True) -> dict[str, Any]:
    """Stub payload — gerçek HTTP çağrısı yapmaz."""
    global _last_stub_export_at
    now = datetime.now(timezone.utc).isoformat()
    _last_stub_export_at = now
    st = status()
    return {
        "adapter": "katip",
        "adapter_version": ADAPTER_VERSION,
        "status": st,
        "dry_run": dry_run,
        "osgb_id": osgb_id,
        "exported_at": now,
        "items": [],
        "note": (
            "KATİP stub export — resmi API çağrısı yapılmadı. "
            "Kimlik bilgisi yoksa status=stub|missing_credentials."
            if st != "configured"
            else "KATİP kimlik bilgisi mevcut; canlı gönderim henüz bağlı değil (scaffold)."
        ),
    }
