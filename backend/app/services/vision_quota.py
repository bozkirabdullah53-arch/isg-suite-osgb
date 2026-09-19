from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AuditLog, User
from app.services.audit import add_audit_log

_TURKEY_TZ = ZoneInfo("Europe/Istanbul")
_QUOTA_ACTION = "vision_ai_quota_consumed"


def turkey_day_utc_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local = current.astimezone(_TURKEY_TZ)
    local_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    local_end = local_start + timedelta(days=1)
    return (
        local_start.astimezone(timezone.utc).replace(tzinfo=None),
        local_end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def ensure_daily_vision_quota(used: int, *, limit: int) -> None:
    if limit <= 0:
        return
    if int(used or 0) >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Günlük {limit} AI fotoğraf analizi hakkınızı kullandınız. "
                "Yeni hak Türkiye saatiyle gece yarısında açılır."
            ),
        )


def consume_daily_vision_quota(
    db: Session,
    user: User,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Reserve one provider-call slot; caller transaction owns commit/rollback."""
    limit = max(0, int(getattr(settings, "vision_daily_limit_per_user", 2) or 0))
    if limit <= 0:
        return {"limit": 0, "used": 0, "remaining": 0}

    db.execute(select(User.id).where(User.id == user.id).with_for_update()).scalar_one()
    start_utc, end_utc = turkey_day_utc_window(now)
    used = int(
        db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.user_id == user.id,
                AuditLog.action == _QUOTA_ACTION,
                AuditLog.created_at >= start_utc,
                AuditLog.created_at < end_utc,
            )
        )
        or 0
    )
    ensure_daily_vision_quota(used, limit=limit)
    add_audit_log(
        db,
        user=user,
        action=_QUOTA_ACTION,
        entity_type="risk_media",
        entity_id=None,
        description=f"AI fotoğraf analiz kotası kullanıldı ({used + 1}/{limit}).",
        module="risk",
    )
    db.flush()
    return {"limit": limit, "used": used + 1, "remaining": max(0, limit - used - 1)}
