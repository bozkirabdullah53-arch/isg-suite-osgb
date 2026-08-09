"""Additive document-date consistency for training outputs.

The training record remains the single source of truth. Final-document dates are
based on the training end date (falling back to start date only for historical
records with no end date) rather than the time a PDF happens to be downloaded.

This module deliberately wraps only the certificate page renderer. It does not
change training records, exam snapshots, participants, certificates, tenant
scope, or database schema.
"""
from __future__ import annotations

from functools import wraps


def training_completion_date(training):
    """Return the persisted training completion date without inventing 'today'."""
    return getattr(training, "end_date", None) or getattr(training, "start_date", None)


def format_training_completion_date(training) -> str:
    value = training_completion_date(training)
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        year, month, day = text[:10].split("-")
        return f"{day}.{month}.{year}"
    return text


def training_completion_date_code(training) -> str:
    value = training_completion_date(training)
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d%m%Y")
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        year, month, day = text[:10].split("-")
        return f"{day}{month}{year}"
    return "".join(ch for ch in text if ch.isdigit())[:8]


def normalize_safety_specialist_title(value: object) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return "İş Güvenliği Uzmanı"
    return text.replace("İSG Uzmanı", "İş Güvenliği Uzmanı").replace("İSG uzmanı", "İş Güvenliği Uzmanı")


class _CertificateTrainingView:
    """Read-only facade correcting only legacy visible certificate terminology."""

    def __init__(self, training):
        self._training = training

    @property
    def instructor_qualification(self):
        return normalize_safety_specialist_title(
            getattr(self._training, "instructor_qualification", None)
        )

    def __getattr__(self, name):
        return getattr(self._training, name)


def _consistent_certificate_number(training, current: str) -> str:
    code = training_completion_date_code(training)
    if not code:
        return current
    raw = str(current or "").strip()
    suffix = "001"
    if raw:
        candidate = raw.rsplit("-", 1)[-1]
        if candidate.isdigit():
            suffix = candidate
    return f"ISG-{code}-{suffix}"


def install_training_document_consistency() -> dict[str, str]:
    """Wrap the active certificate renderer after premium rendering is installed."""
    from app.services import training_pdfs

    current = training_pdfs._draw_certificate_page
    if getattr(current, "_training_document_consistency_active", False):
        return {"certificate_date_consistency": "already-active"}

    @wraps(current)
    def consistent_certificate_renderer(*args, **kwargs):
        training = kwargs.get("training")
        if training is not None:
            completion_text = format_training_completion_date(training)
            if completion_text:
                kwargs["bugun"] = completion_text
            kwargs["belge_no"] = _consistent_certificate_number(
                training,
                kwargs.get("belge_no", ""),
            )
            kwargs["training"] = _CertificateTrainingView(training)
        return current(*args, **kwargs)

    consistent_certificate_renderer._training_document_consistency_active = True
    training_pdfs._draw_certificate_page = consistent_certificate_renderer
    return {"certificate_date_consistency": "active"}
