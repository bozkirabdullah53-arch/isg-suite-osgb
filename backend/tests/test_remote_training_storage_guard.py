from __future__ import annotations

import pytest


def _configure(monkeypatch, guard, *, required: bool = False):
    monkeypatch.setattr(guard.settings, "object_storage_backend", "local")
    monkeypatch.setattr(guard.settings, "object_storage_force_local", False)
    monkeypatch.setattr(guard.settings, "object_storage_remote_required", required)
    guard.reset_remote_training_storage_guard_for_tests()


def test_optional_remote_outage_falls_back_to_working_store(monkeypatch):
    from app.services import remote_training_storage_guard as guard

    _configure(monkeypatch, guard, required=False)
    fallback = object()
    remote = object()
    monkeypatch.setattr(guard, "remote_object_storage_credentials_ok", lambda: True)
    monkeypatch.setattr(guard, "probe_object_storage", lambda: {"status": "unreachable"})
    monkeypatch.setattr(guard, "get_object_store", lambda: fallback)
    monkeypatch.setattr(guard, "get_remote_object_store", lambda: remote)

    assert guard.resilient_remote_training_video_store() is fallback


def test_reachable_remote_is_used_for_large_videos(monkeypatch):
    from app.services import remote_training_storage_guard as guard

    _configure(monkeypatch, guard, required=False)
    fallback = object()
    remote = object()
    monkeypatch.setattr(guard, "remote_object_storage_credentials_ok", lambda: True)
    monkeypatch.setattr(guard, "probe_object_storage", lambda: {"status": "reachable"})
    monkeypatch.setattr(guard, "get_object_store", lambda: fallback)
    monkeypatch.setattr(guard, "get_remote_object_store", lambda: remote)

    assert guard.resilient_remote_training_video_store() is remote


def test_required_remote_outage_fails_closed(monkeypatch):
    from app.services import remote_training_storage_guard as guard

    _configure(monkeypatch, guard, required=True)
    monkeypatch.setattr(guard, "remote_object_storage_credentials_ok", lambda: True)
    monkeypatch.setattr(guard, "probe_object_storage", lambda: {"status": "unreachable"})

    with pytest.raises(RuntimeError, match="erişilemiyor"):
        guard.resilient_remote_training_video_store()


def test_missing_credentials_use_local_when_remote_is_optional(monkeypatch):
    from app.services import remote_training_storage_guard as guard

    _configure(monkeypatch, guard, required=False)
    fallback = object()
    monkeypatch.setattr(guard, "remote_object_storage_credentials_ok", lambda: False)
    monkeypatch.setattr(guard, "get_object_store", lambda: fallback)

    assert guard.resilient_remote_training_video_store() is fallback
