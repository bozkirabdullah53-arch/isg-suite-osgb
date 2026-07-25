"""Local object store + gateway entegrasyonu."""
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.services import object_store as os_mod
from app.services import upload_gateway as gw


@pytest.fixture(autouse=True)
def _reset_store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "object_storage_backend", "local")
    os_mod.reset_object_store_for_tests()
    yield
    os_mod.reset_object_store_for_tests()


def test_local_put_get_delete(tmp_path):
    store = os_mod.get_object_store()
    key = store.put_bytes("7/docs/a.pdf", b"%PDF-1.4")
    assert key == "7/docs/a.pdf"
    assert store.exists(key)
    assert store.get_bytes(key).startswith(b"%PDF")
    path = store.resolve_local_path(key)
    assert path is not None and path.is_file()
    store.delete(key)
    assert not store.exists(key)


def test_path_traversal_rejected():
    store = os_mod.get_object_store()
    with pytest.raises(HTTPException) as exc:
        store.put_bytes("../etc/passwd", b"x")
    assert exc.value.status_code == 400


def test_unknown_backend(monkeypatch):
    monkeypatch.setattr(settings, "object_storage_backend", "mystery")
    os_mod.reset_object_store_for_tests()
    with pytest.raises(RuntimeError, match="Bilinmeyen"):
        os_mod.get_object_store()


def test_local_config_always_ok():
    assert os_mod.object_storage_config_ok() is True
    assert os_mod.storage_backend_label() == "local-v1"


def test_r2_config_requires_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "object_storage_backend", "r2")
    monkeypatch.setattr(settings, "object_storage_bucket", "isg-uploads")
    monkeypatch.setattr(settings, "object_storage_access_key", "ak")
    monkeypatch.setattr(settings, "object_storage_secret_key", "sk")
    monkeypatch.setattr(settings, "object_storage_endpoint", "")
    assert os_mod.object_storage_config_ok() is False
    assert os_mod.storage_backend_label() == "r2-misconfig-v1"
    monkeypatch.setattr(settings, "object_storage_endpoint", "https://x.r2.cloudflarestorage.com")
    assert os_mod.object_storage_config_ok() is True
    assert os_mod.storage_backend_label() == "r2-ready-v1"


def test_s3_without_boto_raises(monkeypatch):
    monkeypatch.setattr(settings, "object_storage_backend", "s3")
    monkeypatch.setattr(settings, "object_storage_bucket", "bucket")
    os_mod.reset_object_store_for_tests()
    # boto3 yoksa ImportError→RuntimeError; varsa bucket ile client kurulabilir —
    # ortamda boto3 olmayabilir; her iki durumda da get_object_store çağrısı güvenli hata vermeli
    # veya başarılı client. Test: backend s3 seçildiğinde Local dönmesin.
    try:
        store = os_mod.get_object_store()
        assert not isinstance(store, os_mod.LocalObjectStore)
    except RuntimeError as exc:
        assert "boto3" in str(exc) or "BUCKET" in str(exc)


def test_gateway_uses_object_store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_gateway_enabled", True)
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    path, name = gw.persist_upload(
        b"%PDF-1.4 data",
        company_id=3,
        extension=".pdf",
        original_name="x.pdf",
        subdir="visits",
    )
    assert name.endswith(".pdf")
    assert path.exists()
    assert Path(tmp_path).resolve() in path.parents


def test_persist_relative_keeps_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_gateway_enabled", True)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    from app.services import object_store as os_mod

    os_mod.reset_object_store_for_tests()
    rel = "9/health/12_abcdef.pdf"
    path = gw.persist_relative(b"%PDF-1.4 x", relative_path=rel, original_name="a.pdf")
    assert path.exists()
    assert path.name.endswith(".pdf")
    assert (tmp_path / "9" / "health").exists()


def test_probe_skips_when_local_no_creds(monkeypatch):
    monkeypatch.setattr(settings, "object_storage_backend", "local")
    monkeypatch.setattr(settings, "object_storage_bucket", None)
    monkeypatch.setattr(settings, "object_storage_access_key", None)
    monkeypatch.setattr(settings, "object_storage_secret_key", None)
    result = os_mod.probe_object_storage()
    assert result["ok"] is True
    assert result["status"] == "local"
    assert result["remote"] == "skipped"
    assert isinstance(os_mod.get_object_store(), os_mod.LocalObjectStore)


def test_probe_reachable_with_mock(monkeypatch):
    import types

    monkeypatch.setattr(settings, "object_storage_backend", "local")
    monkeypatch.setattr(settings, "object_storage_bucket", "isg-uploads")
    monkeypatch.setattr(settings, "object_storage_access_key", "ak")
    monkeypatch.setattr(settings, "object_storage_secret_key", "sk")
    monkeypatch.setattr(settings, "object_storage_endpoint", "https://x.r2.cloudflarestorage.com")
    monkeypatch.setattr(settings, "object_storage_region", "auto")

    class _Client:
        def head_bucket(self, Bucket):  # noqa: N803
            assert Bucket == "isg-uploads"

    class _Boto3:
        @staticmethod
        def client(service, **kwargs):
            assert service == "s3"
            return _Client()

    botocore_config = types.ModuleType("botocore.config")
    botocore_config.Config = lambda *a, **k: object()
    monkeypatch.setitem(__import__("sys").modules, "botocore.config", botocore_config)
    monkeypatch.setitem(__import__("sys").modules, "boto3", _Boto3())

    result = os_mod.probe_object_storage()
    assert result["ok"] is True
    assert result["status"] == "reachable"
    assert isinstance(os_mod.get_object_store(), os_mod.LocalObjectStore)


def test_probe_unreachable_with_mock(monkeypatch):
    import types

    monkeypatch.setattr(settings, "object_storage_backend", "local")
    monkeypatch.setattr(settings, "object_storage_bucket", "isg-uploads")
    monkeypatch.setattr(settings, "object_storage_access_key", "ak")
    monkeypatch.setattr(settings, "object_storage_secret_key", "sk")
    monkeypatch.setattr(settings, "object_storage_endpoint", "https://x.r2.cloudflarestorage.com")

    class _Client:
        def head_bucket(self, Bucket):  # noqa: N803
            raise RuntimeError("boom")

    class _Boto3:
        @staticmethod
        def client(service, **kwargs):
            return _Client()

    botocore_config = types.ModuleType("botocore.config")
    botocore_config.Config = lambda *a, **k: object()
    monkeypatch.setitem(__import__("sys").modules, "botocore.config", botocore_config)
    monkeypatch.setitem(__import__("sys").modules, "boto3", _Boto3())

    result = os_mod.probe_object_storage()
    assert result["ok"] is False
    assert result["status"] == "unreachable"
    assert result["error_class"] == "RuntimeError"


def test_auto_cutover_to_r2_when_reachable(monkeypatch):
    import types

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "object_storage_auto_cutover", True)
    monkeypatch.setattr(settings, "object_storage_force_local", False)
    monkeypatch.setattr(settings, "object_storage_backend", "local")
    monkeypatch.setattr(settings, "object_storage_bucket", "isg-uploads")
    monkeypatch.setattr(settings, "object_storage_access_key", "ak")
    monkeypatch.setattr(settings, "object_storage_secret_key", "sk")
    monkeypatch.setattr(settings, "object_storage_endpoint", "https://abc.r2.cloudflarestorage.com")

    class _Client:
        def head_bucket(self, Bucket):  # noqa: N803
            return None

    class _Boto3:
        @staticmethod
        def client(service, **kwargs):
            return _Client()

    botocore_config = types.ModuleType("botocore.config")
    botocore_config.Config = lambda *a, **k: object()
    monkeypatch.setitem(__import__("sys").modules, "botocore.config", botocore_config)
    monkeypatch.setitem(__import__("sys").modules, "boto3", _Boto3())

    result = os_mod.maybe_auto_cutover_object_storage()
    assert result["status"] == "cutover"
    assert result["backend"] == "r2"
    assert settings.object_storage_backend == "r2"


def test_persistent_disk_and_cutover_gaps(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "object_storage_backend", "local")
    monkeypatch.setattr(settings, "object_storage_bucket", None)
    monkeypatch.setattr(settings, "object_storage_access_key", None)
    monkeypatch.setattr(settings, "object_storage_secret_key", None)
    monkeypatch.setattr(settings, "backup_restore_enabled", False)
    assert os_mod.persistent_disk_label() == "ephemeral-v1"
    gaps = os_mod.infra_cutover_remaining()
    assert "durable_storage" in gaps
    assert os_mod.hardening_complete_label() == "in-progress"

    monkeypatch.setattr(settings, "upload_dir", "/var/data/uploads")
    assert os_mod.persistent_disk_label() == "mounted-v1"
    assert os_mod.infra_cutover_remaining() == []
    assert os_mod.hardening_complete_label() == "complete-v1"
    assert "object_storage_r2_multi_instance" in os_mod.infra_cutover_optional()

    steps = os_mod.infra_cutover_steps()
    disk_step = next(s for s in steps if s["id"] == "persistent_disk")
    assert disk_step["status"] == "done"
    r2_step = next(s for s in steps if s["id"] == "object_storage_r2")
    assert r2_step["status"] == "optional"
    assert r2_step["blocking"] is False
