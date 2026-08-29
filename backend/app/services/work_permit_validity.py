"""Permit-to-work validity-window guards shared by approval/opening flows."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from fastapi import HTTPException


class _PermitWindow(Protocol):
    valid_from: datetime
    valid_until: datetime


def ensure_not_expired_for_activation(permit: _PermitWindow, *, now: datetime | None = None) -> None:
    """Do not advance an already expired permit through approval."""
    current = now or datetime.utcnow()
    if permit.valid_until <= current:
        raise HTTPException(
            409,
            "Çalışma izninin geçerlilik süresi dolmuş. Önce izin süresini uzatın.",
        )


def ensure_open_window(permit: _PermitWindow, *, now: datetime | None = None) -> None:
    """Site opening is allowed only inside the approved permit window."""
    current = now or datetime.utcnow()
    if current < permit.valid_from:
        raise HTTPException(
            409,
            "Çalışma izninin geçerlilik başlangıcı henüz gelmedi.",
        )
    if current >= permit.valid_until:
        raise HTTPException(
            409,
            "Çalışma izninin geçerlilik süresi dolmuş. Önce izin süresini uzatın.",
        )
