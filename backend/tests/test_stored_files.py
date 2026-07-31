"""stored_files helper — local path response."""
from pathlib import Path

import pytest
from fastapi.responses import FileResponse

from app.core.config import settings
from app.services import object_store as os_mod
from app.services.stored_files import response_for_storage_key


@pytest.fixture(autouse=True)
def _reset(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "object_storage_backend", "local")
    os_mod.reset_object_store_for_tests()
    yield
    os_mod.reset_object_store_for_tests()


def test_response_for_local_key(tmp_path):
    store = os_mod.get_object_store()
    store.put_bytes("1/docs/a.pdf", b"%PDF-1.4")
    resp = response_for_storage_key("1/docs/a.pdf", filename="a.pdf", media_type="application/pdf")
    assert isinstance(resp, FileResponse)
    assert Path(resp.path).is_file()
