"""Denetim kaydı yardımcıları (İBYS Veritabanı Değişiklik Prosedürü §8).

``add_audit_log`` her mutasyonda çağrılır; PostgreSQL'de ``audit_logs``
append-only + hash zincirlidir (migration 0121/0122/0125).
"""
from __future__ import annotations

import json

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.entities import AuditLog, User

# Denetimde değişen alanların saklanacağı üst sınır (Text kolonu).
MAX_AUDIT_VALUE_CHARS = 20_000


def request_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    return str(host)[:64] if host else None


def request_user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    try:
        value = headers.get("user-agent")
    except Exception:  # pragma: no cover - savunmacı
        return None
    return str(value)[:255] if value else None


def serialize_audit_value(value) -> str | None:
    """Eski/yeni değeri JSON metne çevirir; sınırı aşan içerik kısaltılır."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(value)
    if len(text) > MAX_AUDIT_VALUE_CHARS:
        return text[:MAX_AUDIT_VALUE_CHARS] + "…[kısaltıldı]"
    return text


def add_audit_log(
    db: Session,
    *,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    description: str | None = None,
    ip_address: str | None = None,
    module: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    company_id: int | None = None,
    user_agent: str | None = None,
) -> None:
    """Denetim satırı ekler (commit çağıranın sorumluluğundadır).

    ``company_id`` verilmezse aktörün firması kullanılır. OSGB yöneticisi
    (``company_id=None``) başka bir firmanın kaydını değiştirdiğinde hedef
    firma açıkça geçirilmelidir; aksi halde kayıt firma filtresinde görünmez.
    """
    resolved_company_id = company_id if company_id is not None else (
        user.company_id if user else None
    )
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            company_id=resolved_company_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=(description or None),
            ip_address=ip_address,
            module=module,
            old_value=old_value,
            new_value=new_value,
            user_agent=user_agent,
        )
    )
