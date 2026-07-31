"""0.9.126 — İBYS/KATİP dry-run export log (harici HTTP yok)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import IntegrationDryRunLog, User
from app.services import ibys_client, katip_client
from app.services.ibys_export import build_ibys_export_summary
from app.services.katip_prep import build_katip_prep

DRY_RUN_VERSION = "log-v1"
AdapterKind = Literal["ibys", "katip"]
VALID_ADAPTERS = frozenset({"ibys", "katip"})


def _record_count(db: Session, adapter: AdapterKind, *, osgb_id: int | None) -> int:
    if adapter == "ibys":
        summary = build_ibys_export_summary(db, osgb_id=osgb_id).get("summary") or {}
        return int(summary.get("companies", 0)) + int(summary.get("employees", 0))
    prep = build_katip_prep(db, osgb_id=osgb_id).get("summary") or {}
    return int(prep.get("active_assignments", 0))


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.isoformat()


def list_recent_dry_runs(
    db: Session,
    *,
    osgb_id: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    stmt = select(IntegrationDryRunLog).order_by(IntegrationDryRunLog.created_at.desc())
    if osgb_id is not None:
        stmt = stmt.where(IntegrationDryRunLog.osgb_id == osgb_id)
    rows = list(db.scalars(stmt.limit(max(1, min(limit, 50)))).all())
    return [
        {
            "id": r.id,
            "who": r.user_email or (f"user:{r.user_id}" if r.user_id else None),
            "user_id": r.user_id,
            "when": _iso(r.created_at),
            "adapter": r.adapter,
            "status": r.status,
            "record_count": int(r.record_count or 0),
            "osgb_id": r.osgb_id,
        }
        for r in rows
    ]


def run_dry_export(
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
        payload = ibys_client.export_payload(osgb_id=osgb_id, dry_run=True)
    else:
        payload = katip_client.export_payload(osgb_id=osgb_id, dry_run=True)

    entry = IntegrationDryRunLog(
        user_id=user.id,
        user_email=(user.email or "").strip() or None,
        osgb_id=osgb_id,
        adapter=kind,
        status="dry_run",
        record_count=count,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {
        "dry_run_version": DRY_RUN_VERSION,
        "stub": True,
        "adapter": kind,
        "status": "dry_run",
        "record_count": count,
        "who": entry.user_email,
        "when": _iso(entry.created_at),
        "osgb_id": osgb_id,
        "log_id": entry.id,
        "payload": {
            "adapter": payload.get("adapter"),
            "adapter_version": payload.get("adapter_version"),
            "status": payload.get("status"),
            "dry_run": True,
            "exported_at": payload.get("exported_at"),
            "item_count": len(payload.get("items") or []),
            "note": payload.get("note"),
        },
        "note": "Dry-run tamamlandı — harici HTTP çağrısı yapılmadı; yalnızca stub payload + log.",
    }
