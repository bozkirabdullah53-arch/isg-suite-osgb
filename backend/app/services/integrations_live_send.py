"""0.9.130 — İBYS/KATİP canlı gönderim (kimlik yoksa network yok; secret dönülmez)."""
from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.entities import IntegrationDryRunLog, User
from app.services import ibys_client, katip_client
from app.services.integrations_dry_run import VALID_ADAPTERS, _iso, _record_count

LIVE_SEND_VERSION = "live-post-v1"
AdapterKind = Literal["ibys", "katip"]


def run_live_send(
    db: Session,
    *,
    adapter: str,
    user: User,
    osgb_id: int | None = None,
) -> dict[str, Any]:
    if adapter not in VALID_ADAPTERS:
        raise ValueError("adapter must be ibys or katip")
    kind: AdapterKind = "ibys" if adapter == "ibys" else "katip"
    count = _record_count(db, kind, osgb_id=osgb_id)

    if kind == "ibys":
        result = ibys_client.live_send(osgb_id=osgb_id, record_count=count)
    else:
        result = katip_client.live_send(osgb_id=osgb_id, record_count=count)

    status = str(result.get("status") or "unknown")
    if status == "missing_credentials":
        log_status = "blocked_no_credentials"
    elif result.get("ok"):
        log_status = "live_sent"
    else:
        log_status = "live_failed"

    entry = IntegrationDryRunLog(
        user_id=user.id,
        user_email=(user.email or "").strip() or None,
        osgb_id=osgb_id,
        adapter=kind,
        status=log_status,
        record_count=count,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {
        "live_send_version": LIVE_SEND_VERSION,
        "adapter": kind,
        "ok": bool(result.get("ok")),
        "status": status,
        "log_status": log_status,
        "http_status": result.get("http_status"),
        "elapsed_ms": result.get("elapsed_ms"),
        "record_count": count,
        "who": entry.user_email,
        "when": _iso(entry.created_at),
        "osgb_id": osgb_id,
        "log_id": entry.id,
        "note": (
            "Kimlik bilgisi yok — harici HTTP çağrısı yapılmadı."
            if status == "missing_credentials"
            else (
                "Canlı gönderim başarılı (HTTP 2xx)."
                if result.get("ok")
                else "Canlı gönderim başarısız — uç nokta yanıtı veya ağ hatası."
            )
        ),
    }
