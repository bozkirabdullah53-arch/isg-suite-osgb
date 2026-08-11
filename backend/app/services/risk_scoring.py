"""Risk method scoring engines.

The existing 5x5 L-type engine is intentionally kept compatible.  Fine-Kinney
uses its own scales and calculation path so selecting it can never silently
fall back to a 5x5 calculation.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import isclose

from app.services.risk_hazop import evaluate_hazop

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

SUPPORTED_SCORING_METHODS = ("5x5_l", "fine_kinney", "hazop")

FINE_KINNEY_PROBABILITIES = (
    (0.1, "Mümkün değil"),
    (0.2, "Beklenmez"),
    (0.5, "Beklenmez fakat mümkün"),
    (1.0, "Mümkün fakat düşük ihtimal"),
    (3.0, "Nadir fakat olabilir"),
    (6.0, "Oldukça mümkün, yüksek ihtimal"),
    (10.0, "Çok kuvvetli ihtimal, beklenir"),
)

FINE_KINNEY_FREQUENCIES = (
    (0.5, "Çok seyrek — yılda bir veya daha az"),
    (1.0, "Oldukça nadir — yılda bir veya birkaç kez"),
    (2.0, "Nadir — ayda bir veya birkaç kez"),
    (3.0, "Ara sıra — haftada bir veya birkaç kez"),
    (6.0, "Sıklıkla — günde bir veya daha fazla"),
    (10.0, "Sürekli — sürekli veya saatte birden fazla"),
)

FINE_KINNEY_SEVERITIES = (
    (1.0, "Ramak kala — çevresel zarar yok"),
    (3.0, "Küçük hasar — dahili ilk yardım"),
    (7.0, "Önemli hasar — dış tedavi / iş günü kaybı"),
    (15.0, "Kalıcı hasar — sakatlık / uzuv kaybı"),
    (40.0, "Ölüm — ölümlü kaza / ciddi çevresel zarar"),
    (100.0, "Felaket — birden fazla ölüm / çevresel felaket"),
)

# Normalized levels keep the existing dashboard, filters and KPI consumers
# compatible.  The method-specific label/action are returned alongside them.
FINE_KINNEY_LEVELS = (
    (20.0, "Kabul Edilebilir", "Kabul Edilebilir Risk", "Mevcut önlemler sürdürülür; yasal ve özel gereklilikler ayrıca uygulanır."),
    (70.0, "Düşük", "Olası Risk", "Gözetim altında tutulmalı; kontrol yöntemleri geliştirilmelidir."),
    (200.0, "Orta", "Ciddi / Önemli Risk", "Dikkatle izlenmeli, makul sürede iyileştirilmeli ve yıllık plana alınmalıdır."),
    (400.0, "Yüksek", "Yüksek Risk", "Kısa dönemde iyileştirilmelidir."),
    (float("inf"), "Çok Yüksek", "Çok Yüksek / Kabul Edilemez Risk", "Çalışma durdurulmalı; risk düşürülmeden başlanmamalıdır."),
)

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
        "method_code": "5x5_l",
        "probability": probability,
        "severity": severity,
        "frequency": None,
        "risk_score": score,
        "risk_level": level,
        "risk_level_label": level,
        "risk_action": {
            "Kabul Edilebilir": "İzleme yeterli olabilir.",
            "Düşük": "Planlı iyileştirme önerilir.",
            "Orta": "Önlemler planlanmalı ve takip edilmelidir.",
            "Yüksek": "Kısa sürede düzeltici faaliyet gerekir.",
            "Çok Yüksek": "İş durdurulabilir; acil önlem zorunlu.",
        }.get(level),
        "term_suggested": suggested,
        "term_days": days,
        "term_date": term_date.isoformat(),
        "term_overridden": overridden,
        "term_label": term_label(days),
        "level_color": LEVEL_COLORS.get(level),
        "probability_label": PROBABILITY_LABELS.get(probability),
        "severity_label": SEVERITY_LABELS.get(severity),
    }


def _choose_fine_value(value: float, choices: tuple[tuple[float, str], ...], label: str) -> float:
    """Validate a Fine-Kinney value against the published discrete scale."""
    numeric = float(value)
    for allowed, _ in choices:
        if isclose(numeric, allowed, rel_tol=0.0, abs_tol=1e-9):
            return allowed
    allowed_text = ", ".join(str(v).rstrip("0").rstrip(".") for v, _ in choices)
    raise ValueError(f"{label} Fine-Kinney skalasında geçerli değil. Seçenekler: {allowed_text}.")


def _fine_level(score: float) -> tuple[str, str, str]:
    for upper_bound, normalized, label, action in FINE_KINNEY_LEVELS:
        if score < upper_bound:
            return normalized, label, action
    # The final row is infinity, so this is defensive only.
    return "Çok Yüksek", "Çok Yüksek / Kabul Edilemez Risk", "Çalışma durdurulmalı; risk düşürülmeden başlanmamalıdır."


def fine_kinney_level_details(score: float) -> tuple[str, str, str]:
    """Return normalized level, method label and action for a stored score."""
    return _fine_level(float(score))


def fine_kinney_term_days(score: float) -> int:
    """Return a planning suggestion, not a statutory deadline."""
    if score >= 400:
        return 0
    if score >= 200:
        return 30
    if score >= 70:
        return 90
    if score >= 20:
        return 180
    return 365


def evaluate_fine_kinney(
    probability: float,
    frequency: float,
    severity: float,
    *,
    term_override_days: int | None = None,
    base_date: date | None = None,
) -> dict:
    """Calculate a Fine-Kinney score using the discrete O/F/Ş scales."""
    p = _choose_fine_value(probability, FINE_KINNEY_PROBABILITIES, "Olasılık")
    f = _choose_fine_value(frequency, FINE_KINNEY_FREQUENCIES, "Frekans")
    s = _choose_fine_value(severity, FINE_KINNEY_SEVERITIES, "Şiddet")
    score = round(p * f * s, 2)
    level, level_label, action = _fine_level(score)
    suggested = fine_kinney_term_days(score)
    overridden = term_override_days is not None and term_override_days != suggested
    days = suggested if term_override_days is None else int(term_override_days)
    start = base_date or date.today()
    term_date = start if days == 0 else start + timedelta(days=days)
    return {
        "method_code": "fine_kinney",
        "probability": p,
        "frequency": f,
        "severity": s,
        "risk_score": score,
        "risk_level": level,
        "risk_level_label": level_label,
        "risk_action": action,
        "term_suggested": suggested,
        "term_days": days,
        "term_date": term_date.isoformat(),
        "term_overridden": overridden,
        "term_label": "Hemen Durdur" if days == 0 else ("24 Saat" if days == 1 else f"{days} Gün"),
        "level_color": LEVEL_COLORS.get(level),
        "probability_label": dict(FINE_KINNEY_PROBABILITIES)[p],
        "frequency_label": dict(FINE_KINNEY_FREQUENCIES)[f],
        "severity_label": dict(FINE_KINNEY_SEVERITIES)[s],
    }


def evaluate_method(
    method_code: str | None,
    probability: float | None,
    severity: float | None,
    *,
    frequency: float | None = None,
    hazop_data: dict | None = None,
    term_override_days: int | None = None,
    base_date: date | None = None,
) -> dict:
    """Dispatch to an implemented method without silently changing methods."""
    code = (method_code or "5x5_l").strip()
    if code == "5x5_l":
        if probability is None or severity is None:
            raise ValueError("5x5 yöntemi için olasılık ve şiddet değerleri zorunludur.")
        if float(probability) != int(float(probability)) or float(severity) != int(float(severity)):
            raise ValueError("5x5 yöntemi için olasılık ve şiddet 1–5 arasında tam sayı olmalıdır.")
        if not 1 <= int(float(probability)) <= 5 or not 1 <= int(float(severity)) <= 5:
            raise ValueError("5x5 yöntemi için olasılık ve şiddet 1–5 arasında olmalıdır.")
        return evaluate(
            int(probability),
            int(severity),
            term_override_days=term_override_days,
            base_date=base_date,
        )
    if code == "fine_kinney":
        if probability is None or severity is None:
            raise ValueError("Fine-Kinney için olasılık ve şiddet değerleri zorunludur.")
        if frequency is None:
            raise ValueError("Fine-Kinney için frekans değeri zorunludur.")
        return evaluate_fine_kinney(
            probability,
            frequency,
            severity,
            term_override_days=term_override_days,
            base_date=base_date,
        )
    if code == "hazop":
        if frequency is not None:
            raise ValueError("HAZOP yönteminde frekans alanı kullanılmaz.")
        if term_override_days is not None:
            raise ValueError("HAZOP termin önerisi öncelikten türetilir; sayısal override kullanılamaz.")
        return evaluate_hazop(hazop_data or {}, base_date=base_date)
    raise ValueError(f"Bu risk değerlendirme yöntemi henüz aktif değil: {code}.")


def meta_payload() -> dict:
    return {
        "probability_labels": PROBABILITY_LABELS,
        "severity_labels": SEVERITY_LABELS,
        "affected_groups": AFFECTED_GROUPS,
        "statuses": RISK_STATUSES,
        "level_colors": LEVEL_COLORS,
        "matrix": "5x5",
        "formula": "risk_score = probability × severity",
        "method_code": "5x5_l",
        "risk_level_labels": {level: level for level in LEVEL_COLORS},
    }


def fine_kinney_meta_payload() -> dict:
    """UI metadata for the implemented Fine-Kinney workspace."""
    return {
        "method_code": "fine_kinney",
        "formula": "risk_score = probability × frequency × severity",
        "probability_axis": "Olasılık",
        "frequency_axis": "Frekans / maruziyet sıklığı",
        "severity_axis": "Şiddet",
        "probability_defs": [
            {"value": value, "label": label} for value, label in FINE_KINNEY_PROBABILITIES
        ],
        "frequency_defs": [
            {"value": value, "label": label} for value, label in FINE_KINNEY_FREQUENCIES
        ],
        "severity_defs": [
            {"value": value, "label": label} for value, label in FINE_KINNEY_SEVERITIES
        ],
        "levels": [
            {
                "min_exclusive": None if idx == 0 else FINE_KINNEY_LEVELS[idx - 1][0],
                "max_exclusive": upper if upper != float("inf") else None,
                "level": normalized,
                "label": label,
                "action": action,
            }
            for idx, (upper, normalized, label, action) in enumerate(FINE_KINNEY_LEVELS)
        ],
        "level_colors": LEVEL_COLORS,
        "planning_note": "Termin günleri yazılımın planlama önerisidir; yasal süre yerine geçmez.",
    }
