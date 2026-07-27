"""Ortak test yardımcıları."""
from __future__ import annotations

import pytest


@pytest.fixture()
def release_flags() -> dict:
    """Özellik bayrağı kaydı (P1-07 sonrası).

    Public /health yalnızca status/service/version/environment döner; bayrak
    kaydı global_admin'e açık /api/v1/system/infra-detail ucundadır.
    """
    from app.services.release_status import infra_detail_payload

    return infra_detail_payload()
