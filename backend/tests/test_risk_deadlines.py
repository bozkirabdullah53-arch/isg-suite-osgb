from datetime import date

import pytest

from app.services.risk_deadlines import imported_deadline
from app.services.risk_excel_import import _parse_term_days


@pytest.mark.parametrize("text,kind,days,due", [
    ("Sürekli izleme", "continuous", None, None),
    ("Sürekli kontrol", "continuous", None, None),
    ("SÜREKLİ İZLEME", "continuous", None, None),
    ("30 gün / Sürekli izleme", "days", 30, date(2026, 7, 9)),
    ("Derhal / En geç 3 gün", "days", 3, date(2026, 6, 12)),
    ("7 gün", "days", 7, date(2026, 6, 16)),
    ("Derhal", "days", 0, date(2026, 6, 9)),
    ("2 hafta", "days", 14, date(2026, 6, 23)),
    ("24 saat", "days", 1, date(2026, 6, 10)),
    ("30.09.2026", "date", 113, date(2026, 9, 30)),
    ("2026-09-30", "date", 113, date(2026, 9, 30)),
    ("31.02.2026", "unset", None, None),
    ("", "unset", None, None),
    ("Daha sonra belirlenecek", "unset", None, None),
])
def test_excel_deadline_preserves_source_meaning(text, kind, days, due):
    assert imported_deadline(text, date(2026, 6, 9)) == {"kind": kind, "days": days, "date": due}


def test_duration_without_source_date_does_not_invent_an_anchor():
    assert imported_deadline("7 gün")["date"] is None
    assert _parse_term_days("2026-09-30") is None
    assert _parse_term_days("Sürekli izleme") is None
