"""Sağlık gözetimi yardımcıları — İSG PRO 2026 parity."""
from __future__ import annotations

from datetime import date, timedelta

# Meslek anahtar kelimesi → önerilen tetkik / maruziyet (PRO SAGLIK_MESLEK_TETKIK_ONERILERI portu)
MESLEK_TETKIK: dict[str, dict] = {
    "aku": {
        "label": "Akü / Kurşun",
        "tests": ["Kan kurşun", "Odyometri", "Solunum fonksiyon", "Akciğer grafisi"],
        "exposures": ["Kurşun", "Asit buharı", "Gürültü"],
    },
    "kaynak": {
        "label": "Kaynak",
        "tests": ["Odyometri", "Solunum fonksiyon", "Akciğer grafisi", "Göz muayenesi"],
        "exposures": ["Metal dumanı", "UV", "Gürültü"],
    },
    "boya": {
        "label": "Boya / Kimyasal",
        "tests": ["Solunum fonksiyon", "Karaciğer enzimleri", "Akciğer grafisi"],
        "exposures": ["Çözücü buharı", "İzosiyanat", "Toz"],
    },
    "forklift": {
        "label": "Forklift / Taşıma",
        "tests": ["Görme", "İşitme", "Kas-iskelet değerlendirme"],
        "exposures": ["Titreşim", "Gürültü", "Ergonomi"],
    },
    "vinc": {
        "label": "Vinç / Yüksekte",
        "tests": ["Görme", "Denge", "Kan şekeri"],
        "exposures": ["Yükseklik", "Gürültü"],
    },
    "elektrik": {
        "label": "Elektrik",
        "tests": ["Görme", "Nörolojik değerlendirme", "EKG"],
        "exposures": ["Elektrik çarpması riski", "Alan kısıtı"],
    },
    "toz": {
        "label": "Tozlu ortam",
        "tests": ["Solunum fonksiyon", "Akciğer grafisi", "Odyometri"],
        "exposures": ["Toz", "Silika", "Gürültü"],
    },
    "gurultu": {
        "label": "Gürültülü ortam",
        "tests": ["Odyometri", "Tinnitus sorgulama"],
        "exposures": ["Gürültü"],
    },
    "lab": {
        "label": "Laboratuvar",
        "tests": ["Kan biyokimya", "Solunum fonksiyon", "Deri muayenesi"],
        "exposures": ["Kimyasal", "Biyolojik ajan"],
    },
    "ofis": {
        "label": "Ofis / İdari",
        "tests": ["Görme", "Genel muayene"],
        "exposures": ["Ekran", "Ergonomi"],
    },
}

JOB_ALIASES: list[tuple[str, str]] = [
    ("aku", "aku"), ("akü", "aku"), ("kursun", "aku"), ("kurşun", "aku"),
    ("kaynak", "kaynak"), ("welding", "kaynak"),
    ("boya", "boya"), ("boyacı", "boya"), ("kimyasal", "boya"),
    ("forklift", "forklift"), ("transpalet", "forklift"), ("operatör", "forklift"),
    ("vinç", "vinc"), ("vinc", "vinc"), ("crane", "vinc"), ("yüksekte", "vinc"),
    ("elektrik", "elektrik"), ("elektrikçi", "elektrik"),
    ("toz", "toz"), ("çimento", "toz"), ("taş", "toz"),
    ("gürültü", "gurultu"), ("gurultu", "gurultu"),
    ("lab", "lab"), ("laboratuvar", "lab"),
    ("ofis", "ofis"), ("muhasebe", "ofis"), ("idari", "ofis"), ("sekreter", "ofis"),
]


def suggest_for_job(job_title: str | None, department: str | None = None) -> dict:
    text = f"{job_title or ''} {department or ''}".casefold()
    matched = []
    tests: list[str] = []
    exposures: list[str] = []
    for alias, key in JOB_ALIASES:
        if alias in text and key not in matched:
            matched.append(key)
            info = MESLEK_TETKIK[key]
            for t in info["tests"]:
                if t not in tests:
                    tests.append(t)
            for e in info["exposures"]:
                if e not in exposures:
                    exposures.append(e)
    if not matched:
        info = MESLEK_TETKIK["ofis"]
        return {
            "matched": ["ofis"],
            "label": info["label"],
            "suggested_tests": info["tests"],
            "exposures": info["exposures"],
        }
    labels = [MESLEK_TETKIK[k]["label"] for k in matched]
    return {
        "matched": matched,
        "label": ", ".join(labels),
        "suggested_tests": tests,
        "exposures": exposures,
    }


def health_period_years(hazard_class: str | None) -> int:
    h = (hazard_class or "").casefold()
    if "çok" in h or "cok" in h:
        return 1
    if "tehlike" in h and "az" not in h:
        return 3
    return 5


def default_next_exam(exam_date: date, hazard_class: str | None) -> date:
    years = health_period_years(hazard_class)
    try:
        return exam_date.replace(year=exam_date.year + years)
    except ValueError:
        return exam_date + timedelta(days=365 * years)


def evaluate_blood_lead(value: float | None, ref: float | None = None) -> str | None:
    if value is None:
        return None
    limit = ref if ref is not None else 30.0
    if value > limit * 1.5:
        return "kritik"
    if value > limit:
        return "yuksek"
    if value > limit * 0.8:
        return "izlem"
    return "normal"
