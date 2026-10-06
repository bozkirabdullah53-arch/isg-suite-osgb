from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException


def test_turkey_calendar_day_is_converted_to_utc_window():
    from app.services.vision_quota import turkey_day_utc_window

    start, end = turkey_day_utc_window(datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc))

    assert start == datetime(2026, 9, 13, 21, 0)
    assert end == datetime(2026, 9, 14, 21, 0)


def test_daily_quota_allows_first_two_and_blocks_third():
    from app.services.vision_quota import ensure_daily_vision_quota

    ensure_daily_vision_quota(0, limit=2)
    ensure_daily_vision_quota(1, limit=2)

    with pytest.raises(HTTPException) as exc:
        ensure_daily_vision_quota(2, limit=2)

    assert exc.value.status_code == 429
    assert "Günlük 2 AI fotoğraf analizi" in str(exc.value.detail)


def test_daily_quota_can_be_disabled_with_zero_limit():
    from app.services.vision_quota import ensure_daily_vision_quota

    ensure_daily_vision_quota(999, limit=0)


def test_default_vision_model_and_daily_limit_are_cost_controlled():
    from app.core.config import Settings

    cfg = Settings(_env_file=None)

    assert cfg.vision_api_model == "openai/gpt-5.6-sol"
    assert cfg.field_ai_model == "openai/gpt-5.6-sol"
    assert cfg.vision_daily_limit_per_user == 2
