from __future__ import annotations

import pytest

from app.core.config import settings, validate_runtime_settings
from app.services import object_store as storage


class _FailingRemote:
    def put_bytes(self, key: str, content: bytes) -> str:
        _ = key, content
        raise ConnectionError("remote unavailable")

    def get_bytes(self, key: str) -> bytes:
        _ = key
        raise FileNotFoundError

    def exists(self, key: str) -> bool:
        _ = key
        return False

    def delete(self, key: str) -> None:
        _ = key
        raise ConnectionError("remote unavailable")

    def resolve_local_path(self, key: str):
        _ = key
        return None


class _WorkingRemote:
    def __init__(self):
        self.data: dict[str, bytes] = {}

    def put_bytes(self, key: str, content: bytes) -> str:
        self.data[key] = content
        return key

    def get_bytes(self, key: str) -> bytes:
        return self.data[key]

    def exists(self, key: str) -> bool:
        return key in self.data

    def delete(self, key: str) -> None:
        self.data.pop(key, None)

    def resolve_local_path(self, key: str):
        _ = key
        return None


def test_optional_dual_mirror_failure_keeps_local_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "object_storage_remote_required", False)
    local = storage.LocalObjectStore(tmp_path)
    dual = storage.DualObjectStore(local=local, remote=_FailingRemote())

    assert dual.put_bytes("company/1/report.pdf", b"new") == "company/1/report.pdf"
    assert local.get_bytes("company/1/report.pdf") == b"new"


def test_required_dual_mirror_failure_removes_new_local_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "object_storage_remote_required", True)
    local = storage.LocalObjectStore(tmp_path)
    dual = storage.DualObjectStore(local=local, remote=_FailingRemote())

    with pytest.raises(RuntimeError, match="dosya kabul edilmedi"):
        dual.put_bytes("company/1/report.pdf", b"new")

    assert local.exists("company/1/report.pdf") is False


def test_required_dual_mirror_failure_restores_previous_local_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "object_storage_remote_required", True)
    local = storage.LocalObjectStore(tmp_path)
    local.put_bytes("company/1/report.pdf", b"previous")
    dual = storage.DualObjectStore(local=local, remote=_FailingRemote())

    with pytest.raises(RuntimeError):
        dual.put_bytes("company/1/report.pdf", b"replacement")

    assert local.get_bytes("company/1/report.pdf") == b"previous"


def test_required_remote_delete_failure_keeps_local_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "object_storage_remote_required", True)
    local = storage.LocalObjectStore(tmp_path)
    local.put_bytes("company/1/report.pdf", b"keep")
    dual = storage.DualObjectStore(local=local, remote=_FailingRemote())

    with pytest.raises(ConnectionError):
        dual.delete("company/1/report.pdf")

    assert local.get_bytes("company/1/report.pdf") == b"keep"


def test_required_dual_success_writes_both_copies(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "object_storage_remote_required", True)
    local = storage.LocalObjectStore(tmp_path)
    remote = _WorkingRemote()
    dual = storage.DualObjectStore(local=local, remote=remote)

    dual.put_bytes("company/1/report.pdf", b"same")

    assert local.get_bytes("company/1/report.pdf") == b"same"
    assert remote.get_bytes("company/1/report.pdf") == b"same"


def test_production_required_remote_storage_needs_credentials(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", "strong-production-secret-key-at-least-32-chars")
    monkeypatch.setattr(settings, "object_storage_remote_required", True)
    monkeypatch.setattr(settings, "object_storage_force_local", False)
    monkeypatch.setattr(settings, "object_storage_bucket", None)
    monkeypatch.setattr(settings, "object_storage_access_key", None)
    monkeypatch.setattr(settings, "object_storage_secret_key", None)
    monkeypatch.setattr(settings, "object_storage_endpoint", None)
    monkeypatch.setattr(settings, "object_storage_region", None)

    with pytest.raises(RuntimeError, match="bucket"):
        validate_runtime_settings()


def test_production_required_remote_storage_rejects_force_local(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", "strong-production-secret-key-at-least-32-chars")
    monkeypatch.setattr(settings, "object_storage_remote_required", True)
    monkeypatch.setattr(settings, "object_storage_force_local", True)

    with pytest.raises(RuntimeError, match="FORCE_LOCAL"):
        validate_runtime_settings()


def test_required_auto_cutover_rejects_unreachable_remote(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "object_storage_remote_required", True)
    monkeypatch.setattr(settings, "object_storage_force_local", False)
    monkeypatch.setattr(settings, "object_storage_auto_cutover", True)
    monkeypatch.setattr(settings, "object_storage_backend", "local")
    monkeypatch.setattr(settings, "object_storage_bucket", "bucket")
    monkeypatch.setattr(settings, "object_storage_access_key", "access")
    monkeypatch.setattr(settings, "object_storage_secret_key", "secret")
    monkeypatch.setattr(settings, "object_storage_endpoint", "https://example.invalid")
    monkeypatch.setattr(storage, "probe_object_storage", lambda: {"status": "unreachable"})

    with pytest.raises(RuntimeError, match="probe"):
        storage.maybe_auto_cutover_object_storage()


def test_durability_readiness_is_secret_free(monkeypatch):
    monkeypatch.setattr(settings, "object_storage_remote_required", True)
    monkeypatch.setattr(settings, "object_storage_backend", "dual")
    monkeypatch.setattr(settings, "object_storage_bucket", "sensitive-bucket")
    monkeypatch.setattr(settings, "object_storage_access_key", "sensitive-access")
    monkeypatch.setattr(settings, "object_storage_secret_key", "sensitive-secret")
    monkeypatch.setattr(settings, "object_storage_endpoint", "https://r2.example")

    result = storage.object_storage_durability_readiness(probe=False)
    rendered = repr(result)

    assert result["required"] is True
    assert result["remote_ready"] is True
    assert result["ready"] is True
    assert "sensitive-bucket" not in rendered
    assert "sensitive-access" not in rendered
    assert "sensitive-secret" not in rendered
