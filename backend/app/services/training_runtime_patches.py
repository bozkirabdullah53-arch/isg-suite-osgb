"""Source-controlled runtime patches for approved training document behavior.

The project historically rewrote Python source files during Render builds. This
module installs the same approved behavior in memory, idempotently, so the code
executed in production remains traceable to the repository.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

OLD_HEADINGS = (
    "4. FAALİYETİN GENEL TEHLİKE VE RİSKLERİ",
    "4. Faaliyetin Genel Tehlike ve Riskleri",
    "4. Faaliyetin genel tehlike ve riskleri",
    "FAALİYETİN GENEL TEHLİKE VE RİSKLERİ",
    "Faaliyetin genel tehlike ve riskleri",
)
NEW_HEADING = "4. İŞE VE İŞYERİNE ÖZGÜ RİSKLER VE RİSK DEĞERLENDİRMESİNE DAYALI KONULAR"


def _replace_heading(value: Any) -> Any:
    if isinstance(value, str):
        result = value
        for old in OLD_HEADINGS:
            result = result.replace(old, NEW_HEADING)
        return result
    if isinstance(value, list):
        return [_replace_heading(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_heading(item) for item in value)
    if isinstance(value, dict):
        return {
            _replace_heading(key): _replace_heading(item)
            for key, item in value.items()
        }
    return value


def _patch_training_topics() -> str:
    from app.services import training_topics

    for name, value in list(vars(training_topics).items()):
        if name.startswith("__"):
            continue
        replaced = _replace_heading(value)
        if replaced is not value:
            setattr(training_topics, name, replaced)

    wrapped_count = 0
    for function_name in (
        "egitim_konularini_hazirla",
        "katilim_formu_konu_ozeti",
    ):
        original = getattr(training_topics, function_name, None)
        if not callable(original) or getattr(original, "_fourth_heading_patched", False):
            continue

        @wraps(original)
        def wrapped(*args, __original=original, **kwargs):
            return _replace_heading(__original(*args, **kwargs))

        wrapped._fourth_heading_patched = True
        setattr(training_topics, function_name, wrapped)
        wrapped_count += 1

    return "active" if wrapped_count else "already-active"


def _patch_certificate_renderer() -> str:
    from app.services import training_pdfs
    from app.services.training_pdf_premium import draw_certificate_page

    current = training_pdfs._draw_certificate_page
    if getattr(current, "_premium_renderer_active", False):
        return "already-active"

    @wraps(current)
    def premium_renderer(*args, **kwargs):
        kwargs["tp"] = training_pdfs
        return draw_certificate_page(*args, **kwargs)

    premium_renderer._premium_renderer_active = True
    training_pdfs._draw_certificate_page = premium_renderer
    return "active"


def install_training_runtime_patches() -> dict[str, str]:
    """Install approved training topic and certificate behavior idempotently."""
    return {
        "topics": _patch_training_topics(),
        "premium_certificate": _patch_certificate_renderer(),
    }
