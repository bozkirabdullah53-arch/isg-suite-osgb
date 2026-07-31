"""0.9.125+ — İBYS/KATİP adapter durum özeti + son dry-run/live logları."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services import ibys_client, katip_client
from app.services.integrations_dry_run import list_recent_dry_runs

STATUS_VERSION = "stub-clients-v1"


def build_integrations_status(
    db: Session | None = None,
    *,
    osgb_id: int | None = None,
) -> dict[str, Any]:
    ibys_st = ibys_client.status()
    katip_st = katip_client.status()
    ibys_cfg = ibys_client.validate_config()
    katip_cfg = katip_client.validate_config()
    any_configured = bool(ibys_cfg["configured"] or katip_cfg["configured"])
    last_dry_runs: list[dict[str, Any]] = []
    if db is not None:
        last_dry_runs = list_recent_dry_runs(db, osgb_id=osgb_id, limit=8)
    return {
        "status_version": STATUS_VERSION,
        "stub": not any_configured,
        "note": (
            "İBYS / İSG-KATİP adapter — dry-run/probe/live-send. "
            "Kimlik yoksa canlı POST yapılmaz; secrets asla dönülmez."
        ),
        "adapters": {
            "ibys": {
                "configured": bool(ibys_cfg["configured"]),
                "status": ibys_st,
                "last_stub_export_at": ibys_client.last_stub_export_at(),
                "last_live_send_at": ibys_client.last_live_send_at(),
            },
            "katip": {
                "configured": bool(katip_cfg["configured"]),
                "status": katip_st,
                "last_stub_export_at": katip_client.last_stub_export_at(),
                "last_live_send_at": katip_client.last_live_send_at(),
            },
        },
        "summary": {
            "ibys_configured": bool(ibys_cfg["configured"]),
            "katip_configured": bool(katip_cfg["configured"]),
            "any_configured": any_configured,
            "dry_run_count": len(last_dry_runs),
            "live_send_ready": any_configured,
        },
        "last_dry_runs": last_dry_runs,
    }
