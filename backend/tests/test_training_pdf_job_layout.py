from __future__ import annotations

from types import SimpleNamespace

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm

from app.services import training_pdf_premium as premium
from app.services import training_pdfs


class _RecordingCanvas:
    def __init__(self):
        self.operations = []

    def setFont(self, font, size):
        self.font = (font, size)

    def stringWidth(self, text, font, size):
        return len(str(text)) * size * 0.52

    def drawString(self, x, y, text):
        self.operations.append(("left", x, y, text, self.font))

    def drawRightString(self, x, y, text):
        self.operations.append(("right", x, y, text, self.font))


def test_premium_certificate_job_value_cannot_overlap_label():
    canvas = _RecordingCanvas()
    tp = SimpleNamespace(
        _FONT=training_pdfs._FONT,
        _FONT_B=training_pdfs._FONT_B,
        _fit=training_pdfs._fit,
    )
    page_width, _ = landscape(A4)

    premium._draw_job_field(
        canvas,
        page_width,
        100,
        "Gıda üretim destek personeli",
        tp=tp,
    )

    label = next(op for op in canvas.operations if op[0] == "left")
    value = next(op for op in canvas.operations if op[0] == "right")
    label_end = label[1] + canvas.stringWidth(label[3], *label[4])
    value_start = value[1] - canvas.stringWidth(value[3], *value[4])

    assert label[3] == "Görevi:"
    assert value[3]
    assert label_end < value_start
    assert value_start >= page_width - 70 * mm
