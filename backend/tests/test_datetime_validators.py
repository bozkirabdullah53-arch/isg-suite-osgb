import pytest

from app.schemas.validators import parse_optional_datetime


def test_parse_optional_datetime_iso_local():
    assert parse_optional_datetime("2026-07-30T12:00").year == 2026


def test_parse_optional_datetime_tr_format():
    dt = parse_optional_datetime("30.07.2026 14:30")
    assert dt.day == 30 and dt.month == 7 and dt.hour == 14


def test_parse_optional_datetime_empty():
    assert parse_optional_datetime("") is None
    assert parse_optional_datetime("—") is None
