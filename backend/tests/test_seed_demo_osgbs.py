"""Demo OSGB seed — production'da silinenler geri gelmesin."""
from __future__ import annotations

from app.core.config import settings
from app.services.seed import _demo_seed_allowed, seed_demo_osgbs


def test_demo_seed_disabled_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "seed_demo_osgbs", False)
    assert _demo_seed_allowed() is False


def test_demo_seed_enabled_when_flag_set(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "seed_demo_osgbs", True)
    assert _demo_seed_allowed() is True


def test_seed_demo_osgbs_noop_when_disabled(monkeypatch):
    class _Dummy:
        def scalar(self, *_a, **_k):
            raise AssertionError("DB'ye dokunulmamalı")

        def commit(self):
            raise AssertionError("commit olmamalı")

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "seed_demo_osgbs", False)
    assert seed_demo_osgbs(_Dummy()) == []
