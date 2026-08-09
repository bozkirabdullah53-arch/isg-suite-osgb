"""Safe retirement/anonymization for detached user accounts.

A user row can be referenced by audit/history records. For that reason an orphan
account is not hard-deleted: login credentials and personal identifiers are
irreversibly replaced while the numeric user id remains available for referential
integrity and historical evidence.
"""
from __future__ import annotations

import secrets
from uuid import uuid4

from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.entities import IsgProfessional, User, UserRole


def _active_membership_count(db: Session, table_name: str, user_id: int) -> int:
    """Count active memberships; tolerate legacy/test schemas without the table."""
    bind = db.get_bind()
    if bind is None or not inspect(bind).has_table(table_name):
        return 0
    return int(
        db.scalar(
            text(
                f"SELECT count(*) FROM {table_name} "
                "WHERE user_id = :user_id AND is_active IS TRUE"
            ),
            {"user_id": int(user_id)},
        )
        or 0
    )


def orphan_account_state(db: Session, user: User) -> dict[str, object]:
    """Return strict scope state used before an orphan account may be retired."""
    email = str(getattr(user, "email", "") or "").strip().lower()
    professional = None
    if email:
        professional = db.scalar(
            select(IsgProfessional)
            .where(func.lower(IsgProfessional.email) == email)
            .order_by(IsgProfessional.id)
            .limit(1)
        )

    org_memberships = _active_membership_count(db, "organization_memberships", int(user.id))
    workplace_memberships = _active_membership_count(db, "workplace_memberships", int(user.id))

    has_scope = bool(
        user.role == UserRole.GLOBAL_ADMIN
        or getattr(user, "osgb_id", None)
        or getattr(user, "company_id", None)
        or professional
        or org_memberships
        or workplace_memberships
    )
    eligible = bool(
        user.role != UserRole.GLOBAL_ADMIN
        and not bool(getattr(user, "is_active", False))
        and not has_scope
    )
    return {
        "scope_valid": has_scope,
        "eligible": eligible,
        "professional_id": getattr(professional, "id", None),
        "organization_memberships": org_memberships,
        "workplace_memberships": workplace_memberships,
    }


def anonymize_orphan_user(db: Session, user: User) -> str:
    """Irreversibly retire one strictly orphaned, inactive, non-global user."""
    state = orphan_account_state(db, user)
    if not bool(state["eligible"]):
        raise ValueError("Kullanıcı yetim hesap temizliği için uygun değil.")

    original_email = str(user.email or "").strip()
    user.email = f"deleted-user-{int(user.id)}-{uuid4().hex[:12]}@invalid.local"
    user.full_name = "Silinmiş Kullanıcı"
    user.hashed_password = get_password_hash(secrets.token_urlsafe(64))
    user.is_active = False
    user.company_id = None
    user.osgb_id = None
    user.failed_login_count = 0
    user.locked_until = None
    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.mfa_recovery_hashes = None
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    db.flush()
    return original_email