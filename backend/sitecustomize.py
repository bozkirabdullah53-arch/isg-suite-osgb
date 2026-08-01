"""Production-safe wording patch for the fourth İSG training topic heading.

Only the heading text is normalized. Topic contents, order, durations and all
other legal/document data remain unchanged.
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
    """Recursively replace only the old fourth-section heading text."""
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


def _patch_training_topics() -> None:
    try:
        from app.services import training_topics
    except Exception:
        return

    # Normalize module-level constants/collections without touching topic bodies.
    for name, value in list(vars(training_topics).items()):
        if name.startswith("__"):
            continue
        replaced = _replace_heading(value)
        if replaced is not value:
            try:
                setattr(training_topics, name, replaced)
            except Exception:
                pass

    # Normalize dynamically produced structures used by PDF generation.
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


_patch_training_topics()
