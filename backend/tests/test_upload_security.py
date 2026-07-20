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
