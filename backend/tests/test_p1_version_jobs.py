"""P1-11 tek sürüm kaynağı + P1-10 yedek job iskeleti."""
from app.core.version import APP_VERSION
from app.main import app
from app.api import system as system_api
from app.services.job_queue import JobStatus, enqueue


def test_app_version_single_source():
    assert app.version == APP_VERSION
    assert system_api.APP_VERSION == APP_VERSION
    # OpenAPI / health marker
    assert APP_VERSION.startswith("0.9.")


def test_enqueue_accepts_kwargs(monkeypatch):
    monkeypatch.setattr("app.services.job_queue.async_jobs_enabled", lambda: False)

    def work(*, n):
        return n + 1

    rec = enqueue("kw", work, n=41)
    assert rec.status == JobStatus.DONE
    assert rec.result == 42


def test_async_jobs_auto_on_with_redis(monkeypatch):
    from app.core import config as cfg
    from app.services import job_queue as jq

    monkeypatch.setattr(cfg.settings, "async_jobs_force_off", False)
    monkeypatch.setattr(cfg.settings, "async_jobs_enabled", False)
    monkeypatch.setattr(cfg.settings, "redis_url", "redis://localhost:6379/0")
    assert jq.async_jobs_enabled() is True
    monkeypatch.setattr(cfg.settings, "async_jobs_force_off", True)
    assert jq.async_jobs_enabled() is False
    monkeypatch.setattr(cfg.settings, "async_jobs_force_off", False)
    monkeypatch.setattr(cfg.settings, "redis_url", None)
    assert jq.async_jobs_enabled() is False


def test_site_qr_ttl_default_short():
    from app.core.config import settings

    assert int(settings.site_qr_ephemeral_ttl_minutes) <= 5
