"""JWT denylist — logout sonrası jti iptali."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import TokenDenylist


def is_jti_revoked(db: Session, jti: str | None) -> bool:
    if not jti:
        return False
    row = db.scalar(select(TokenDenylist.id).where(TokenDenylist.jti == jti).limit(1))
    return row is not None


def revoke_jti(
    db: Session,
    *,
    jti: str,
    user_id: int | None,
    expires_at: datetime,
) -> None:
    if not jti:
        return
    existing = db.scalar(select(TokenDenylist).where(TokenDenylist.jti == jti).limit(1))
    if existing:
        return
    db.add(
        TokenDenylist(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            revoked_at=datetime.utcnow(),
        )
    )


def bump_token_version(user) -> int:
    """Şifre değişince / logout-all ile tüm eski JWT'leri düşürür."""
    current = int(getattr(user, "token_version", 0) or 0)
    user.token_version = current + 1
    return user.token_version


def prune_expired_denylist(db: Session, *, limit: int = 200) -> int:
    """Süresi dolmuş denylist kayıtlarını siler (best-effort, sınırlı batch)."""
    from sqlalchemy import delete

    now = datetime.utcnow()
    expired_ids = list(
        db.scalars(select(TokenDenylist.id).where(TokenDenylist.expires_at < now).limit(limit)).all()
    )
    if not expired_ids:
        return 0
    result = db.execute(delete(TokenDenylist).where(TokenDenylist.id.in_(expired_ids)))
    return int(result.rowcount or 0)
