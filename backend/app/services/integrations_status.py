"""0.9.125 — İBYS/KATİP entegrasyon adapter durum özeti (boolean + stub timestamps)."""
from __future__ import annotations

from typing import Any

from app.services import ibys_client, katip_client

STATUS_VERSION = "stub-clients-v1"


def build_integrations_status() -> dict[str, Any]:
    ibys_st = ibys_client.status()
    katip_st = katip_client.status()
    ibys_cfg = ibys_client.validate_config()
    katip_cfg = katip_client.validate_config()
    return {
        "status_version": STATUS_VERSION,
        "stub": True,
        "note": (
            "İBYS / İSG-KATİP adapter scaffold — gerçek resmi API çağrısı yok. "
            "Yalnızca yapılandırma durumu (boolean) ve son stub export zamanı."
        ),
        "adapters": {
            "ibys": {
                "configured": bool(ibys_cfg["configured"]),
                "status": ibys_st,
                "last_stub_export_at": ibys_client.last_stub_export_at(),
            },
            "katip": {
                "configured": bool(katip_cfg["configured"]),
                "status": katip_st,
                "last_stub_export_at": katip_client.last_stub_export_at(),
            },
        },
        "summary": {
            "ibys_configured": bool(ibys_cfg["configured"]),
            "katip_configured": bool(katip_cfg["configured"]),
            "any_configured": bool(ibys_cfg["configured"] or katip_cfg["configured"]),
        },
    }
