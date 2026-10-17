"""İsteğe bağlı hata izleme (Sentry).

- SENTRY_DSN tanımlı değilse hiçbir şey yapılmaz ve sentry_sdk yüklenmez.
- KVKK: kişisel veri gönderilmez. İstek gövdesi, başlıklar, çerezler ve kullanıcı
  bilgisi olay kaydından çıkarılır; send_default_pii kapalıdır.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_PERSONAL_KEYS = ("request", "user")


def _scrub_event(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Olay kaydından kişisel veri taşıyabilecek alanları çıkarır."""
    for key in _PERSONAL_KEYS:
        event.pop(key, None)
    return event


def init_error_monitoring() -> bool:
    """DSN varsa Sentry'yi başlatır; başlatıldıysa True döner."""
    dsn = (settings.sentry_dsn or "").strip()
    if not dsn:
        return False

    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=(settings.environment or "production").strip(),
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=_scrub_event,
    )
    logger.info("Hata izleme (Sentry) etkin.")
    return True
