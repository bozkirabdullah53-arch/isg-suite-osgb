import pytest
from fastapi import HTTPException

from app.services.upload_security import assert_safe_upload


def test_pdf_magic_accepts():
    assert_safe_upload(b"%PDF-1.7\n", ".pdf", "a.pdf")


def test_exe_magic_rejected_even_as_pdf():
    with pytest.raises(HTTPException) as ei:
        assert_safe_upload(b"MZ\x90\x00", ".pdf", "x.pdf")
    assert ei.value.status_code == 400


def test_png_mismatch_rejected():
    with pytest.raises(HTTPException) as ei:
        assert_safe_upload(b"XXXX", ".png", "x.png")
    assert ei.value.status_code == 400


def test_clamav_skipped_when_disabled(monkeypatch):
    monkeypatch.setattr("app.services.upload_security.is_clamav_configured", lambda: False)
    assert_safe_upload(b"%PDF-1.7\n", ".pdf", "ok.pdf")


def test_clamav_rejects_malware(monkeypatch):
    monkeypatch.setattr("app.services.upload_security.is_clamav_configured", lambda: True)
    monkeypatch.setattr(
        "app.services.upload_security.scan_bytes",
        lambda _content: (False, "stream: Eicar-Test-Signature FOUND"),
    )
    with pytest.raises(HTTPException) as ei:
        assert_safe_upload(b"%PDF-1.7\n", ".pdf", "bad.pdf")
    assert ei.value.status_code == 400


def test_clamav_accepts_clean(monkeypatch):
    monkeypatch.setattr("app.services.upload_security.is_clamav_configured", lambda: True)
    monkeypatch.setattr(
        "app.services.upload_security.scan_bytes",
        lambda _content: (True, "stream: OK"),
    )
    assert_safe_upload(b"%PDF-1.7\n", ".pdf", "clean.pdf")
