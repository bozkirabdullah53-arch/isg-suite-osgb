"""Türkiye iş günü hesaplamaları."""

from datetime import date, timedelta

import holidays


def add_turkish_business_days(start_date: date, business_days: int) -> date:
    """Return the date after the requested number of Turkish business days.

    The start date is not counted. Weekends and dates published in the
    Turkish public-holiday calendar are excluded.
    """
    if business_days < 0:
        raise ValueError("business_days negatif olamaz")
    if business_days == 0:
        return start_date

    tr_holidays = holidays.country_holidays("TR")
    current = start_date
    remaining = business_days

    while remaining:
        current += timedelta(days=1)
        if current.weekday() >= 5 or current in tr_holidays:
            continue
        remaining -= 1

    return current
