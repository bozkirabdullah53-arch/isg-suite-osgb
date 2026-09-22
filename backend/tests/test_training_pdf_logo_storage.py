from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


# 1x1 PNG; keeping the fixture inline makes the storage-path test independent
# from the repository's uploaded-file directory.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def test_training_logo_is_materialized_from_object_storage_for_pdf(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services import training_pdfs

    relative = "17/training-logos/165_logo.png"

    class FakeObjectStore:
        def exists(self, key):
            return key == relative

        def get_bytes(self, key):
            assert key == relative
            return _PNG

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "upload_gateway_enabled", True)
    monkeypatch.setattr(training_pdfs, "get_object_store", lambda: FakeObjectStore())

    training = SimpleNamespace(logo_path=relative)
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)

    assert training_pdfs._draw_logo(
        pdf,
        training,
        x=24,
        y=24,
        max_w=80,
        max_h=50,
    ) is True
    pdf.save()

    cached = tmp_path / "uploads" / relative
    assert cached.read_bytes() == _PNG
    assert b"/Subtype /Image" in output.getvalue()
