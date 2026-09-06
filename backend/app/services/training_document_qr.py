"""Public QR verification helpers for training documents.

The QR code contains only the public, read-only verification URL. It never
embeds employee data, access tokens, or a PDF payload, so old document and
authentication flows remain unchanged.
"""
from __future__ import annotations

from io import BytesIO
from urllib.parse import quote

from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from app.core.config import settings


def training_verification_url(code: str | None) -> str | None:
    """Return the canonical public verification URL for a training code."""
    clean = str(code or "").strip().upper()
    origin = str(getattr(settings, "frontend_origin", "") or "").strip().rstrip("/")
    if not clean or not origin:
        return None
    return f"{origin}/?egitim-dogrula={quote(clean, safe='')}"


def _qr_image(payload: str) -> ImageReader | None:
    """Build a ReportLab image without making QR generation a hard import."""
    try:
        import qrcode
    except ImportError:
        return None

    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=2,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return ImageReader(buffer)
    except Exception:
        # A PDF must remain printable even if an optional image backend
        # cannot be initialized. The human-readable verification code stays
        # in the document and the application continues to work.
        return None


def draw_training_qr(
    c,
    code: str | None,
    *,
    x: float,
    y: float,
    size: float = 17 * mm,
) -> bool:
    """Draw a small QR box and return whether it was rendered.

    x and y are the lower-left coordinates of the QR image. The
    caller chooses the safe document area, which lets the existing attendance
    and certificate layouts stay unchanged when a legacy record has no code.
    """
    url = training_verification_url(code)
    if not url:
        return False
    image = _qr_image(url)
    if image is None:
        return False

    c.saveState()
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(0.72, 0.76, 0.82)
    c.setLineWidth(0.35)
    padding = 1.2 * mm
    c.roundRect(
        x - padding,
        y - padding,
        size + 2 * padding,
        size + 2 * padding,
        1.2 * mm,
        fill=1,
        stroke=1,
    )
    c.drawImage(
        image,
        x,
        y,
        width=size,
        height=size,
        preserveAspectRatio=True,
        anchor="sw",
        mask="auto",
    )
    c.restoreState()
    return True
