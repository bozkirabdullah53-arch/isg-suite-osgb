"""Ortak test yardımcıları."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_rate_limit():
    """Hız sınırlayıcı testler arasında taşmasın.

    Sayaç süreç genelinde paylaşıldığı için login yoğun bir dosya, sonraki
    dosyaların login'lerini 429 ile düşürüyordu (sıra/süre bağımlı rastgele hata).
    """
    from app.core.rate_limit import reset_rate_limit_store_for_tests

    reset_rate_limit_store_for_tests()
    yield


@pytest.fixture()
def release_flags() -> dict:
    """Özellik bayrağı kaydı (P1-07 sonrası).

    Public /health yalnızca status/service/version/environment döner; bayrak
    kaydı global_admin'e açık /api/v1/system/infra-detail ucundadır.
    """
    from app.services.release_status import infra_detail_payload

    return infra_detail_payload()
