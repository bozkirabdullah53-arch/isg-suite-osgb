"""İşyeri saha QR doğrulama — kalıcı kod + geçici (TTL) oturum."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings

QR_PREFIX = "ISGSUITE:WP:"
QR_TEMP_PREFIX = "ISGSUITE:WPTEMP:"


def generate_site_verify_code() -> str:
    return secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12].upper()


def generate_ephemeral_token() -> str:
    return secrets.token_urlsafe(18).replace("-", "").replace("_", "")[:24].upper()


def build_qr_payload(company_id: int, code: str) -> str:
    return f"{QR_PREFIX}{company_id}:{code}"


def build_ephemeral_qr_payload(company_id: int, token: str) -> str:
    return f"{QR_TEMP_PREFIX}{company_id}:{token}"


def parse_site_code(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if upper.startswith(QR_TEMP_PREFIX):
        return ""
    if upper.startswith(QR_PREFIX):
        tail = text[len(QR_PREFIX) :]
        parts = tail.split(":", 1)
        if len(parts) == 2:
            return parts[1].strip().upper()
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def parse_ephemeral(raw: str) -> tuple[int | None, str]:
    """Döner: (company_id|None, token). Geçersizse (None, '')."""
    text = (raw or "").strip()
    if not text:
        return None, ""
    upper = text.upper()
    if upper.startswith(QR_TEMP_PREFIX):
        tail = text[len(QR_TEMP_PREFIX) :]
        parts = tail.split(":", 1)
        if len(parts) == 2:
            try:
                cid = int(parts[0].strip())
            except ValueError:
                return None, ""
            token = re.sub(r"[^A-Za-z0-9]", "", parts[1]).upper()
            return cid, token
    # Ham token (yalnızca A-Z0-9) — company_id çağıran eşleştirir
    bare = re.sub(r"[^A-Za-z0-9]", "", text).upper()
    if 16 <= len(bare) <= 32:
        return None, bare
    return None, ""


def codes_match(company_code: str | None, raw: str | None) -> bool:
    """Kalıcı işyeri kodu eşleşmesi — boş şirket kodu fail-closed (P0-05)."""
    if not company_code or not str(company_code).strip():
        return False
    submitted = parse_site_code(raw or "")
    return bool(submitted) and submitted == company_code.strip().upper()


def create_ephemeral_session(
    db: Session,
    *,
    company_id: int,
    created_by_id: int | None = None,
    ttl_minutes: int | None = None,
):
    """Önceki kullanılmamış oturumları iptal eder; yeni TTL'li oturum oluşturur."""
    from app.models.entities import SiteQrSession

    minutes = ttl_minutes if ttl_minutes is not None else int(settings.site_qr_ephemeral_ttl_minutes)
    minutes = max(5, min(minutes, 24 * 60))
    now = datetime.utcnow()

    db.execute(
        update(SiteQrSession)
        .where(
            SiteQrSession.company_id == company_id,
            SiteQrSession.used_at.is_(None),
            SiteQrSession.revoked_at.is_(None),
            SiteQrSession.expires_at > now,
        )
        .values(revoked_at=now)
    )

    token = generate_ephemeral_token()
    row = SiteQrSession(
        company_id=company_id,
        token=token,
        expires_at=now + timedelta(minutes=minutes),
        created_by_id=created_by_id,
        created_at=now,
    )
    db.add(row)
    db.flush()
    return row


def consume_ephemeral_token(db: Session, company_id: int, raw: str | None) -> bool:
    """Geçerli geçici QR ise used_at işaretler ve True döner."""
    from app.models.entities import SiteQrSession

    parsed_cid, token = parse_ephemeral(raw or "")
    if not token:
        return False
    if parsed_cid is not None and parsed_cid != company_id:
        return False

    now = datetime.utcnow()
    row = db.scalar(
        select(SiteQrSession).where(
            SiteQrSession.company_id == company_id,
            SiteQrSession.token == token,
            SiteQrSession.used_at.is_(None),
            SiteQrSession.revoked_at.is_(None),
            SiteQrSession.expires_at > now,
        )
    )
    if not row:
        return False
    row.used_at = now
    return True
