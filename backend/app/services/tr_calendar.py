"""Türkiye resmi tatilleri ve iş günü kaydırma — yıllık plan hedef tarihleri için."""
from __future__ import annotations

from datetime import date, timedelta

# Sabit resmi tatiller (ay, gün)
_FIXED: tuple[tuple[int, int], ...] = (
    (1, 1),   # Yılbaşı
    (4, 23),  # Ulusal Egemenlik ve Çocuk Bayramı
    (5, 1),   # Emek ve Dayanışma Günü
    (5, 19),  # Atatürk'ü Anma, Gençlik ve Spor Bayramı
    (7, 15),  # Demokrasi ve Millî Birlik Günü
    (8, 30),  # Zafer Bayramı
    (10, 29), # Cumhuriyet Bayramı
)

# Dini bayramlar (yıl → başlangıç tarihleri, gün sayısı ile genişletilir)
# Kaynak: Diyanet / resmi ilanlar — 2024–2031
_RELIGIOUS_START: dict[int, list[tuple[date, int]]] = {
    2024: [
        (date(2024, 4, 10), 3),   # Ramazan Bayramı
        (date(2024, 6, 16), 4),   # Kurban Bayramı
    ],
    2025: [
        (date(2025, 3, 30), 3),
        (date(2025, 6, 6), 4),
    ],
    2026: [
        (date(2026, 3, 20), 3),
        (date(2026, 5, 27), 4),
    ],
    2027: [
        (date(2027, 3, 9), 3),
        (date(2027, 5, 16), 4),
    ],
    2028: [
        (date(2028, 2, 26), 3),
        (date(2028, 5, 5), 4),
    ],
    2029: [
        (date(2029, 2, 14), 3),
        (date(2029, 4, 24), 4),
    ],
    2030: [
        (date(2030, 2, 4), 3),
        (date(2030, 4, 13), 4),
    ],
    2031: [
        (date(2031, 1, 24), 3),
        (date(2031, 4, 3), 4),
    ],
}


def _expand_spans(spans: list[tuple[date, int]]) -> set[date]:
    out: set[date] = set()
    for start, days in spans:
        for i in range(days):
            out.add(start + timedelta(days=i))
    return out


def official_holidays(year: int) -> set[date]:
    """Verilen yılın resmi tatil günleri (hafta sonu hariç sabit + dini bayram)."""
    days = {date(year, m, d) for m, d in _FIXED}
    # 29 Ekim arifesi (28 Ekim öğleden sonra) — tam gün tatil değil; plana tam gün olarak eklemiyoruz
    for y in (year - 1, year, year + 1):
        spans = _RELIGIOUS_START.get(y)
        if not spans:
            continue
        for d in _expand_spans(spans):
            if d.year == year:
                days.add(d)
    return days


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # Cumartesi=5, Pazar=6


def is_non_working_day(d: date, holidays: set[date] | None = None) -> bool:
    hol = holidays if holidays is not None else official_holidays(d.year)
    return is_weekend(d) or d in hol


def next_workday(d: date, holidays: set[date] | None = None) -> date:
    """d tatil/hafta sonuysa sonraki ilk iş gününe kaydır."""
    cur = d
    for _ in range(21):
        year_hol = holidays if (holidays is not None and cur.year == d.year) else official_holidays(cur.year)
        if not is_non_working_day(cur, year_hol):
            return cur
        cur += timedelta(days=1)
    return d


def plan_target_date(year: int, month: int, preferred_day: int = 15) -> date:
    """
    Aylık plan hedefi: tercihen preferred_day; hafta sonu veya resmi tatilse
    aynı ay içinde sonraki iş gününe, ay bitiyorsa önceki iş gününe kaydır.
    """
    import calendar as cal

    last = cal.monthrange(year, month)[1]
    day = min(max(1, preferred_day), last)
    hol = official_holidays(year)
    candidate = date(year, month, day)

    if not is_non_working_day(candidate, hol):
        return candidate

    forward = candidate
    while forward.month == month and is_non_working_day(forward, hol):
        forward += timedelta(days=1)
    if forward.month == month and not is_non_working_day(forward, hol):
        return forward

    backward = candidate
    while backward.month == month and is_non_working_day(backward, hol):
        backward -= timedelta(days=1)
    if backward.month == month and not is_non_working_day(backward, hol):
        return backward

    end = date(year, month, last)
    while end.day > 1 and is_non_working_day(end, hol):
        end -= timedelta(days=1)
    return end
