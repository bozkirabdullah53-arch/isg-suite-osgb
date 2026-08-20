from datetime import date

import pytest

from app.services.business_days import add_turkish_business_days


def test_adds_three_business_days_from_monday() -> None:
    assert add_turkish_business_days(date(2026, 8, 17), 3) == date(2026, 8, 20)


def test_skips_weekend_when_calculating_three_business_days() -> None:
    assert add_turkish_business_days(date(2026, 8, 19), 3) == date(2026, 8, 24)


def test_skips_turkish_public_holiday() -> None:
    # 23 Nisan 2026 Perşembe günüdür; Çarşamba olayının üçüncü iş günü
    # 28 Nisan Salı gününe denk gelir.
    assert add_turkish_business_days(date(2026, 4, 22), 3) == date(2026, 4, 28)


def test_zero_days_returns_start_date() -> None:
    start = date(2026, 8, 20)
    assert add_turkish_business_days(start, 0) == start


def test_negative_days_are_rejected() -> None:
    with pytest.raises(ValueError):
        add_turkish_business_days(date(2026, 8, 20), -1)
