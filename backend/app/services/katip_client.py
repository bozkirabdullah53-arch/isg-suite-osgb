"""0.9.125+ — İSG-KATİP API adapter scaffold (stub) + safe connection probe.

Gerçek resmi KATİP sözleşmesi / kimlik bilgisi yokken yalnızca yapılandırma
doğrulama ve stub export payload üretir. Secrets asla loglanmaz / dönülmez.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from app.core.config import settings

ADAPTER_VERSION = "stub-clients-v1"
PROBE_VERSION = "live-check-v1"
PROBE_TIMEOUT_S = 5.0
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


def _http_probe(url: str) -> dict[str, Any]:
    """Reachability check — URL/key asla dönülmez."""
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=PROBE_TIMEOUT_S, follow_redirects=True) as client:
            try:
                resp = client.head(url)
                if resp.status_code == 405:
                    resp = client.get(url)
            except httpx.HTTPError:
                resp = client.get(url)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": True,
            "status": "reachable",
            "http_status": resp.status_code,
            "elapsed_ms": elapsed_ms,
        }
    except httpx.TimeoutException:
        return {
            "ok": False,
            "status": "timeout",
            "http_status": None,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception:
        return {
            "ok": False,
            "status": "unreachable",
            "http_status": None,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }


def probe() -> dict[str, Any]:
    """Safe live connection probe. Secrets asla loglanmaz / dönülmez."""
    now = datetime.now(timezone.utc).isoformat()
    cfg = validate_config()
    if not cfg["configured"]:
        return {
            "adapter": "katip",
            "ok": False,
            "status": "missing_credentials",
            "adapter_version": ADAPTER_VERSION,
            "probe_version": PROBE_VERSION,
            "probed_at": now,
        }
    url = (settings.katip_api_url or "").strip()
    result = _http_probe(url)
    return {
        "adapter": "katip",
        "ok": result["ok"],
        "status": result["status"],
        "http_status": result.get("http_status"),
        "elapsed_ms": result.get("elapsed_ms"),
        "adapter_version": ADAPTER_VERSION,
        "probe_version": PROBE_VERSION,
        "probed_at": now,
    }


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
