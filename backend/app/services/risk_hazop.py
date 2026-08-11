"""HAZOP yöntemi için kılavuz kelime, doğrulama ve öncelik motoru.

HAZOP bir çarpım matrisi değildir. Bu modül, yöntemin çekirdeğini oluşturan
parametre/kılavuz kelime/sapma/neden/sonuç/koruma/öneri kayıtlarını doğrular.
Mevcut risk panosunun sıralama ve termin alanlarıyla uyum için ayrıca nitel
bir öncelik karşılığı üretir; raporlarda bu değer açıkça "HAZOP önceliği" olarak
gösterilir.
"""
from __future__ import annotations

from datetime import date, timedelta
from collections.abc import Mapping


HAZOP_GUIDE_WORDS = (
    {"code": "no", "label": "Yok / Hiç", "meaning": "Tasarım amacının hiç gerçekleşmemesi."},
    {"code": "more", "label": "Daha fazla", "meaning": "Parametrenin tasarım değerinden yüksek olması."},
    {"code": "less", "label": "Daha az", "meaning": "Parametrenin tasarım değerinden düşük olması."},
    {"code": "as_well_as", "label": "Bununla birlikte", "meaning": "Tasarım amacına ilave bir durumun eşlik etmesi."},
    {"code": "part_of", "label": "Bir kısmı", "meaning": "Tasarım amacının yalnızca bir bölümünün gerçekleşmesi."},
    {"code": "reverse", "label": "Tersi", "meaning": "Tasarım amacının ters yönde gerçekleşmesi."},
    {"code": "other_than", "label": "Başka / Farklı", "meaning": "Tasarım amacı dışında başka bir durum oluşması."},
    {"code": "early", "label": "Erken", "meaning": "İşlemin veya olayın öngörülenden önce gerçekleşmesi."},
    {"code": "late", "label": "Geç", "meaning": "İşlemin veya olayın öngörülenden sonra gerçekleşmesi."},
    {"code": "before", "label": "Önce", "meaning": "Sıralı adımın önce gerçekleşmesi."},
    {"code": "after", "label": "Sonra", "meaning": "Sıralı adımın sonra gerçekleşmesi."},
)

HAZOP_PARAMETERS = (
    "Debi / akış",
    "Basınç",
    "Sıcaklık",
    "Seviye",
    "Kompozisyon / konsantrasyon",
    "Faz / fiziksel durum",
    "Hız",
    "Süre / zaman",
    "Sıra / işlem adımı",
    "Gerilim / enerji",
    "Yoğunluk",
    "Diğer",
)

HAZOP_PRIORITIES = (
    {
        "code": "low",
        "label": "Düşük öncelik",
        "level": "Düşük",
        "score": 5,
        "term_days": 90,
        "action": "Kayıt altına alınır; mevcut korumalar izlenir ve rutin gözden geçirmede doğrulanır.",
    },
    {
        "code": "medium",
        "label": "Orta öncelik",
        "level": "Orta",
        "score": 10,
        "term_days": 30,
        "action": "İyileştirme önerisi sorumlu ve termin verilerek plana alınmalıdır.",
    },
    {
        "code": "high",
        "label": "Yüksek öncelik",
        "level": "Yüksek",
        "score": 15,
        "term_days": 7,
        "action": "Kısa sürede teknik/idari önlem uygulanmalı ve DÖF ile takip edilmelidir.",
    },
    {
        "code": "critical",
        "label": "Kritik öncelik",
        "level": "Çok Yüksek",
        "score": 25,
        "term_days": 0,
        "action": "Çalışma güvenli hale getirilmeden sürdürülmemeli; acil önlem ve yönetim onayı gerekir.",
    },
)

_GUIDE_WORD_BY_CODE = {item["code"]: item for item in HAZOP_GUIDE_WORDS}
_PRIORITY_BY_CODE = {item["code"]: item for item in HAZOP_PRIORITIES}

_REQUIRED_FIELDS = (
    "node",
    "design_intent",
    "parameter",
    "guide_word",
    "deviation",
    "causes",
    "consequences",
    "safeguards",
)
_MAX_LENGTHS = {
    "node": 300,
    "design_intent": 2000,
    "parameter": 120,
    "guide_word": 40,
    "deviation": 2000,
    "causes": 4000,
    "consequences": 4000,
    "safeguards": 4000,
    "recommendations": 4000,
    "priority": 20,
}


def _clean_text(value: object, field: str, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if len(text) > _MAX_LENGTHS[field]:
        raise ValueError(f"HAZOP {field} alanı çok uzun.")
    if required and len(text) < 2:
        raise ValueError(f"HAZOP {field} alanı zorunludur.")
    return text


def normalize_hazop_data(data: Mapping | None) -> dict[str, str]:
    """Validate and normalize the persisted HAZOP row payload."""
    if not isinstance(data, Mapping):
        raise ValueError("HAZOP çalışma alanı zorunludur.")

    cleaned: dict[str, str] = {}
    for field in _REQUIRED_FIELDS:
        cleaned[field] = _clean_text(data.get(field), field, required=True)
    cleaned["recommendations"] = _clean_text(data.get("recommendations"), "recommendations")

    guide_word = cleaned["guide_word"]
    if guide_word not in _GUIDE_WORD_BY_CODE:
        raise ValueError("HAZOP kılavuz kelimesi geçersiz.")

    priority = _clean_text(data.get("priority") or "medium", "priority", required=True)
    if priority not in _PRIORITY_BY_CODE:
        raise ValueError("HAZOP önceliği geçersiz.")
    cleaned["priority"] = priority
    return cleaned


def guide_word_label(code: str | None) -> str:
    return _GUIDE_WORD_BY_CODE.get(code or "", {}).get("label") or code or "—"


def priority_details(code: str | None) -> dict:
    return _PRIORITY_BY_CODE.get(code or "", _PRIORITY_BY_CODE["medium"])


def evaluate_hazop(data: Mapping, *, base_date: date | None = None) -> dict:
    """Return dashboard-compatible planning fields for a qualitative HAZOP row."""
    normalized = normalize_hazop_data(data)
    priority = priority_details(normalized["priority"])
    days = int(priority["term_days"])
    start = base_date or date.today()
    term_date = start if days == 0 else start + timedelta(days=days)
    return {
        "method_code": "hazop",
        "hazop_data": normalized,
        # These numeric values are compatibility ranks for existing sorting/KPI
        # consumers only; HAZOP reports never present them as a matrix formula.
        "probability": float(priority["score"] // 5),
        "frequency": None,
        "severity": float(priority["score"] // 5),
        "risk_score": float(priority["score"]),
        "risk_level": priority["level"],
        "risk_level_label": priority["label"],
        "risk_action": priority["action"],
        "hazop_priority": normalized["priority"],
        "term_suggested": days,
        "term_days": days,
        "term_date": term_date.isoformat(),
        "term_overridden": False,
        "term_label": "Acil" if days == 0 else f"{days} Gün",
        "level_color": {
            "Düşük": "#2ecc71",
            "Orta": "#f1c40f",
            "Yüksek": "#f39c12",
            "Çok Yüksek": "#e74c3c",
        }.get(priority["level"]),
    }


def hazop_meta_payload() -> dict:
    return {
        "method_code": "hazop",
        "formula": "Kılavuz kelime → sapma → neden → sonuç → koruma → öneri",
        "node_axis": "Proses düğümü",
        "parameter_axis": "Proses parametresi",
        "guide_words": list(HAZOP_GUIDE_WORDS),
        "parameters": list(HAZOP_PARAMETERS),
        "priority_options": [
            {
                "code": item["code"],
                "label": item["label"],
                "level": item["level"],
                "term_days": item["term_days"],
            }
            for item in HAZOP_PRIORITIES
        ],
        "planning_note": "HAZOP önceliği, çalışma planlama sınıfıdır; mevzuattaki yenileme sürelerinin yerine geçmez.",
        "method_note": "HAZOP satırı; proses düğümü, tasarım amacı, parametre ve kılavuz kelime üzerinden sapmayı inceler.",
        "reference": "IEC 61882:2016 — HAZOP studies — Application guide",
    }
