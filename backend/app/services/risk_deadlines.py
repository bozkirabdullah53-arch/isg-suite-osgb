"""Preserve the meaning of imported deadlines instead of inventing a due date."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta


def _fold(text: str | None) -> str:
    value = unicodedata.normalize("NFKD", str(text or "").lower().replace("ı", "i"))
    return "".join(char for char in value if not unicodedata.combining(char)).strip()


def is_continuous_term(text: str | None) -> bool:
    value = _fold(text)
    # A deadline followed by ongoing monitoring still has a real due date.
    return bool(re.fullmatch(r"surekli(?:\s+(?:izleme|kontrol)(?:\s*[/+ve ]+\s*(?:izleme|kontrol))?)?", value))


def imported_deadline(text: str | None, assessment_date: date | None = None) -> dict:
    value = _fold(text)
    if is_continuous_term(text):
        return {"kind": "continuous", "days": None, "date": None}
    for pattern, order in ((r"(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"),
                           (r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", "dmy")):
        match = re.fullmatch(pattern, value)
        if match:
            parts = list(map(int, match.groups()))
            try:
                due = date(*parts) if order == "ymd" else date(parts[2], parts[1], parts[0])
            except ValueError:
                return {"kind": "unset", "days": None, "date": None}
            return {"kind": "date", "days": (due - assessment_date).days if assessment_date else None, "date": due}
    days = None
    match = re.search(r"\b(\d+)\s*(gun|hafta|saat)\b", value)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        days = amount * 7 if unit == "hafta" else (amount + 23) // 24 if unit == "saat" else amount
    elif re.fullmatch(r"\d+", value):
        days = int(value)
    elif not re.search(r"\d", value) and any(word in value for word in ("derhal", "hemen", "acil")):
        days = 0
    if days is None or days > 3650:
        return {"kind": "unset", "days": None, "date": None}
    return {"kind": "days", "days": days,
            "date": assessment_date + timedelta(days=days) if assessment_date else None}
