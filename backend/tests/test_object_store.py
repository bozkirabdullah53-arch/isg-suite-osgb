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
