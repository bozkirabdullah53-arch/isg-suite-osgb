from pathlib import Path

SERVICE = '''from __future__ import annotations

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
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"patch point missing: {label}")
    return text.replace(old, new, 1)


Path("backend/app/services/vision_quota.py").write_text(SERVICE, encoding="utf-8")

config_path = Path("backend/app/core/config.py")
config = config_path.read_text(encoding="utf-8")
config = config.replace('vision_api_model: str = "openai/gpt-5.4-mini"', 'vision_api_model: str = "openai/gpt-5.6-sol"')
config = config.replace(
    'vision_max_image_mb: int = 10',
    'vision_max_image_mb: int = 10\n    # Kullanıcı başına Türkiye takvim gününde ücretli AI fotoğraf analiz kotası. 0 = sınırsız.\n    vision_daily_limit_per_user: int = 2',
)
config = config.replace('field_ai_model: str = "openai/gpt-5.4-mini"', 'field_ai_model: str = "openai/gpt-5.6-sol"')
config_path.write_text(config, encoding="utf-8")

render_path = Path("render.yaml")
render = render_path.read_text(encoding="utf-8")
render = render.replace('value: "openai/gpt-5.4-mini"', 'value: "openai/gpt-5.6-sol"')
needle = '      - key: VISION_API_TIMEOUT_SEC\n        value: "90"\n'
if "VISION_DAILY_LIMIT_PER_USER" not in render:
    render = replace_once(
        render,
        needle,
        needle + '      - key: VISION_DAILY_LIMIT_PER_USER\n        value: "2"\n',
        "render daily quota",
    )
render_path.write_text(render, encoding="utf-8")

risks_path = Path("backend/app/api/risks.py")
risks = risks_path.read_text(encoding="utf-8")
if "from app.services.vision_quota import consume_daily_vision_quota" not in risks:
    risks = replace_once(
        risks,
        "from app.services.upload_security import assert_safe_upload\n",
        "from app.services.upload_security import assert_safe_upload\nfrom app.services.vision_quota import consume_daily_vision_quota\n",
        "quota import",
    )

flag_block = '''    if not vision_analysis_active():
        raise HTTPException(501, "Saha AI analizi şu anda kapalı (VISION_ANALYSIS_ENABLED).")

    raw = await file.read()
'''
quota_block = '''    if not vision_analysis_active():
        raise HTTPException(501, "Saha AI analizi şu anda kapalı (VISION_ANALYSIS_ENABLED).")

    quota = consume_daily_vision_quota(db, user)
    raw = await file.read()
'''
risks = replace_once(risks, flag_block, quota_block, "async quota")
risks = replace_once(
    risks,
    '''    except Exception as exc:
        try:
            temp_path.unlink(missing_ok=True)
''',
    '''    except Exception as exc:
        db.rollback()
        try:
            temp_path.unlink(missing_ok=True)
''',
    "enqueue rollback",
)
risks = replace_once(
    risks,
    '''    db.commit()
    return {"job_id": job.id, "status": getattr(job.status, "value", str(job.status))}
''',
    '''    db.commit()
    return {
        "job_id": job.id,
        "status": getattr(job.status, "value", str(job.status)),
        "daily_ai_quota": quota,
    }
''',
    "quota response",
)
risks = replace_once(risks, flag_block, quota_block, "sync quota")
risks = replace_once(
    risks,
    '''    row, media = _load_media(db, risk_id, media_id)
    ensure_access(db, user, row.company_id)

    image_bytes = None
''',
    '''    row, media = _load_media(db, risk_id, media_id)
    ensure_access(db, user, row.company_id)
    consume_daily_vision_quota(db, user)

    image_bytes = None
''',
    "persisted quota",
)
risks_path.write_text(risks, encoding="utf-8")
