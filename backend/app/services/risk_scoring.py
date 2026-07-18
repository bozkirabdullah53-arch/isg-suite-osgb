"""5x5 risk skoru, seviye ve termin — İSG PRO 2026 risk modülünden."""
from __future__ import annotations

from datetime import date, timedelta

PROBABILITY_LABELS = {
    1: "Çok Küçük",
    2: "Küçük",
    3: "Orta",
    4: "Yüksek",
    5: "Çok Yüksek",
}

SEVERITY_LABELS = {
    1: "Çok Hafif",
    2: "Hafif",
    3: "Orta",
    4: "Ağır",
    5: "Çok Ağır",
}

AFFECTED_GROUPS = ["Çalışan", "Ziyaretçi", "Müteahhit", "Çevre"]

RISK_STATUSES = ["Açık", "Tamamlandı", "İptal", "Revize"]

LEVEL_COLORS = {
    "Kabul Edilebilir": "#95a5a6",
    "Düşük": "#2ecc71",
    "Orta": "#f1c40f",
    "Yüksek": "#f39c12",
    "Çok Yüksek": "#e74c3c",
}


def compute_score(probability: int, severity: int) -> int:
    return int(probability) * int(severity)


def risk_level(score: int) -> str:
    if score <= 4:
        return "Kabul Edilebilir"
    if score <= 9:
        return "Düşük"
    if score <= 14:
        return "Orta"
    if score <= 19:
        return "Yüksek"
    return "Çok Yüksek"


def suggested_term_days(score: int) -> int:
    if score == 25:
        return 0
    if score >= 20:
        return 1
    if score >= 18:
        return 3
    if score >= 15:
        return 7
    if score >= 12:
        return 15
    if score >= 10:
        return 30
    if score >= 8:
        return 60
    return 90


def term_label(days: int) -> str:
    if days == 0:
        return "Hemen Durdur"
    if days == 1:
        return "24 Saat"
    return f"{days} Gün"


def evaluate(
    probability: int,
    severity: int,
    *,
    term_override_days: int | None = None,
    base_date: date | None = None,
) -> dict:
    """Skor + seviye + termin hesapla."""
    score = compute_score(probability, severity)
    level = risk_level(score)
    suggested = suggested_term_days(score)
    overridden = term_override_days is not None and term_override_days != suggested
    days = suggested if term_override_days is None else int(term_override_days)
    start = base_date or date.today()
    term_date = start if days == 0 else start + timedelta(days=days)
    return {
        "probability": probability,
        "severity": severity,
        "risk_score": score,
        "risk_level": level,
        "term_suggested": suggested,
        "term_days": days,
        "term_date": term_date.isoformat(),
        "term_overridden": overridden,
        "term_label": term_label(days),
        "level_color": LEVEL_COLORS.get(level),
        "probability_label": PROBABILITY_LABELS.get(probability),
        "severity_label": SEVERITY_LABELS.get(severity),
    }


def meta_payload() -> dict:
    return {
        "probability_labels": PROBABILITY_LABELS,
        "severity_labels": SEVERITY_LABELS,
        "affected_groups": AFFECTED_GROUPS,
        "statuses": RISK_STATUSES,
        "level_colors": LEVEL_COLORS,
        "matrix": "5x5",
        "formula": "risk_score = probability × severity",
    }
