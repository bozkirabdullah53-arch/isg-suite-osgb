"""Upload gateway iskeleti — flag kapalıyken RuntimeError; açılınca güvenli yazma."""
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.services import upload_gateway as gw


def test_persist_upload_blocked_when_flag_off(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_gateway_enabled", False)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    with pytest.raises(RuntimeError, match="upload_gateway_enabled=False"):
        gw.persist_upload(b"%PDF-1.4", company_id=1, extension=".pdf", original_name="a.pdf")


def test_persist_upload_writes_when_flag_on(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_gateway_enabled", True)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    path, name = gw.persist_upload(
        b"%PDF-1.4 hello",
        company_id=42,
        extension=".pdf",
        original_name="rapor.pdf",
        subdir="visits",
    )
    assert path.exists()
    assert name.endswith(".pdf")
    assert path.read_bytes().startswith(b"%PDF")
    assert Path(tmp_path).resolve() in path.parents


def test_persist_upload_rejects_oversized(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_gateway_enabled", True)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_mb", 0)  # 0 MB limit → any content over
    with pytest.raises(HTTPException) as exc:
        gw.persist_upload(b"%PDF-1.4 x", company_id=1, extension=".pdf", original_name="a.pdf")
    assert exc.value.status_code == 413
