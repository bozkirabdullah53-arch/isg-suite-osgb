"""Tamper-evident, append-only audit helpers for occupational health data."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.models.entities import Company, HealthAccessLog, HealthRecord, HealthRecordRevision, User


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def raw_health_snapshot(record: HealthRecord) -> dict[str, Any]:
    """Snapshot raw DB values; encrypted clinical fields remain encrypted."""
    return {
        column.key: getattr(record, column.key)
        for column in sa_inspect(HealthRecord).columns
    }


def append_health_revision(
    db: Session,
    *,
    record: HealthRecord,
    actor: User,
    action: str,
    reason: str | None = None,
) -> HealthRecordRevision:
    previous = db.scalar(
        select(HealthRecordRevision)
        .where(HealthRecordRevision.record_id == record.id)
        .order_by(HealthRecordRevision.version.desc(), HealthRecordRevision.id.desc())
        .limit(1)
    )
    snapshot_json = _canonical(raw_health_snapshot(record))
    created_at = datetime.utcnow()
    payload = {
        "company_id": record.company_id,
        "record_id": record.id,
        "version": record.version,
        "action": action,
        "actor_user_id": actor.id,
        "reason": reason,
        "snapshot_json": snapshot_json,
        "previous_hash": previous.entry_hash if previous else None,
        "created_at": created_at,
    }
    revision = HealthRecordRevision(
        company_id=record.company_id,
        record_id=record.id,
        version=record.version,
        action=action,
        actor_user_id=actor.id,
        reason=reason,
        snapshot_json=snapshot_json,
        previous_hash=payload["previous_hash"],
        entry_hash=_digest(payload),
        created_at=created_at,
    )
    db.add(revision)
    db.flush()
    return revision


def append_health_access(
    db: Session,
    *,
    actor: User,
    company_id: int,
    action: str,
    request: Request | None = None,
    record_id: int | None = None,
    purpose: str = "occupational_health_service",
    metadata: dict[str, Any] | None = None,
) -> HealthAccessLog:
    # Serialize each company's access-log chain.  Without this lock, two
    # concurrent requests could both point at the same previous hash.
    db.execute(
        select(Company.id)
        .where(Company.id == company_id)
        .with_for_update()
    )
    previous = db.scalar(
        select(HealthAccessLog)
        .where(HealthAccessLog.company_id == company_id)
        .order_by(HealthAccessLog.id.desc())
        .limit(1)
    )
    created_at = datetime.utcnow()
    request_path = str(request.url.path)[:500] if request else None
    ip_address = request.client.host[:64] if request and request.client else None
    metadata_json = _canonical(metadata) if metadata else None
    payload = {
        "company_id": company_id,
        "record_id": record_id,
        "actor_user_id": actor.id,
        "action": action,
        "purpose": purpose,
        "request_path": request_path,
        "ip_address": ip_address,
        "metadata_json": metadata_json,
        "previous_hash": previous.entry_hash if previous else None,
        "created_at": created_at,
    }
    event = HealthAccessLog(
        company_id=company_id,
        record_id=record_id,
        actor_user_id=actor.id,
        action=action,
        purpose=purpose,
        request_path=request_path,
        ip_address=ip_address,
        metadata_json=metadata_json,
        previous_hash=payload["previous_hash"],
        entry_hash=_digest(payload),
        created_at=created_at,
    )
    db.add(event)
    db.flush()
    return event


def verify_revision_chain(rows: list[HealthRecordRevision]) -> bool:
    previous_hash: str | None = None
    for row in sorted(rows, key=lambda item: (item.version, item.id)):
        payload = {
            "company_id": row.company_id,
            "record_id": row.record_id,
            "version": row.version,
            "action": row.action,
            "actor_user_id": row.actor_user_id,
            "reason": row.reason,
            "snapshot_json": row.snapshot_json,
            "previous_hash": previous_hash,
            "created_at": row.created_at,
        }
        if row.previous_hash != previous_hash or row.entry_hash != _digest(payload):
            return False
        previous_hash = row.entry_hash
    return True


def verify_access_chain(rows: list[HealthAccessLog]) -> bool:
    previous_hash: str | None = None
    for row in sorted(rows, key=lambda item: item.id):
        payload = {
            "company_id": row.company_id,
            "record_id": row.record_id,
            "actor_user_id": row.actor_user_id,
            "action": row.action,
            "purpose": row.purpose,
            "request_path": row.request_path,
            "ip_address": row.ip_address,
            "metadata_json": row.metadata_json,
            "previous_hash": previous_hash,
            "created_at": row.created_at,
        }
        if row.previous_hash != previous_hash or row.entry_hash != _digest(payload):
            return False
        previous_hash = row.entry_hash
    return True
