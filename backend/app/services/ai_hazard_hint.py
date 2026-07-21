"""
0.9.117 — Tehlike önerisi (keyword-v1); 0.9.122 — keyword-v2 + foto etiket ipucu.

Ücretli AI API yok: Türkçe anahtar kelime → tehlike kategorisi + olasılık + risk foto etiketleri.
Fotoğraf AI (ai_photo_analysis.yaml) sonraki faz; bu MVP saha risk oluşturmayı hızlandırır.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

HINT_ENGINE = "keyword-v2"

# (kategori_adı, olasılık_ipucu 1-5, anahtarlar) — skor = eşleşen anahtar sayısı
_RULES: list[tuple[str, int, tuple[str, ...]]] = [
    (
        "Yüksekte Çalışma Riskleri",
        4,
        (
            "yüksekte",
            "yuksekte",
            "iskele",
            "çatı",
            "cati",
            "düşme",
            "dusme",
            "emniyet kemeri",
            "yaşam hattı",
            "yasam hatti",
            "merdiven",
            "platform",
            "sepetli",
        ),
    ),
    (
        "Yangın ve Patlama Riskleri",
        4,
        (
            "yangın",
            "yangin",
            "patlama",
            "atex",
            "yanıcı",
            "yanici",
            "parlayıcı",
            "parlayici",
            "lpg",
            "doğalgaz",
            "dogalgaz",
            "kıvılcım",
            "kivilcim",
            "sprinkler",
            "alev",
        ),
    ),
    (
        "Elektrik Riskleri",
        4,
        (
            "elektrik",
            "kablo",
            "pano",
            "topraklama",
            "kaçak akım",
            "kacak akim",
            "şok",
            "sok",
            "ark",
            "trafo",
            "gerilim",
            "sigorta",
            "paratoner",
        ),
    ),
    (
        "Kimyasal Riskler",
        4,
        (
            "kimyasal",
            "solvent",
            "asit",
            "baz",
            "boya",
            "vernik",
            "yapıştırıcı",
            "yapistirici",
            "sds",
            "msds",
            "gaz",
            "buhar",
            "toksik",
            "zehir",
            "dökülme",
            "dokulme",
            "asit",
        ),
    ),
    (
        "Biyolojik Riskler",
        3,
        (
            "biyolojik",
            "bakteri",
            "virüs",
            "virus",
            "enfeksiyon",
            "kan",
            "iğne",
            "igne",
            "kesici-delici",
            "hijyen",
            "mikroorganizma",
            "hepatit",
        ),
    ),
    (
        "Ergonomik Riskler",
        3,
        (
            "ergonomi",
            "kaldırma",
            "kaldirma",
            "elle taşıma",
            "elle tasima",
            "tekrarlayan",
            "bel ağrısı",
            "bel agrisi",
            "masa başı",
            "masa basi",
            "ekran",
            "zorlanma",
            "ağır yük",
            "agir yuk",
        ),
    ),
    (
        "Psikososyal Riskler",
        3,
        (
            "stres",
            "mobbing",
            "psikososyal",
            "tükenmişlik",
            "tukenmislik",
            "iş yükü",
            "is yuku",
            "vardiya baskı",
            "taciz",
            "çatışma",
            "catisma",
        ),
    ),
    (
        "Nakliye ve Trafik Riskleri",
        3,
        (
            "trafik",
            "araç",
            "arac",
            "forklift",
            "kamyon",
            "sevkiyat",
            "yükleme",
            "yukleme",
            "boşaltma",
            "bosaltma",
            "adr",
            "yaya yolu",
            "tesis içi trafik",
            "tesis ici trafik",
        ),
    ),
    (
        "İnşaat ve Yapı Riskleri",
        4,
        (
            "inşaat",
            "insaat",
            "şantiye",
            "santiye",
            "kazı",
            "kazi",
            "kalıp",
            "kalip",
            "beton",
            "yıkım",
            "yikim",
            "yapı işleri",
            "yapi isleri",
        ),
    ),
    (
        "Mekanik Riskler",
        4,
        (
            "makine",
            "pres",
            "konveyör",
            "konveyor",
            "kesici",
            "ezilme",
            "sıkışma",
            "sikisma",
            "dönen aksam",
            "donen aksam",
            "koruyucu",
            "vinç",
            "vinc",
            "testere",
            "matkap",
            "kayış",
            "kayis",
        ),
    ),
    (
        "Fiziksel Riskler",
        3,
        (
            "gürültü",
            "gurultu",
            "titreşim",
            "titresim",
            "toz",
            "aydınlatma",
            "aydinlatma",
            "ısı",
            "isi",
            "sıcak",
            "sicak",
            "soğuk",
            "soguk",
            "radyasyon",
            "uv",
            "nem",
            "termal",
            "db",
        ),
    ),
    (
        "Çevresel Riskler",
        2,
        (
            "atık",
            "atik",
            "çevre",
            "cevre",
            "emisyon",
            "atık su",
            "atik su",
            "sızıntı",
            "sizinti",
            "toprak kirliliği",
            "toprak kirliligi",
        ),
    ),
]


# 0.9.122 — metin → risk foto tehlike etiketi (checklist-v1 kodları)
_PHOTO_TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("ppe_missing", ("kkd", "ppe", "baret", "eldiven", "gözlük", "gozluk", "maske", "koruyucu ekipman")),
    ("slippery_floor", ("kaygan", "nemli zemin", "yağ dökül", "yag dokul", "kayma", "zemin")),
    ("electrical", ("elektrik", "kablo", "pano", "topraklama", "gerilim", "şok", "sok")),
    ("work_at_height", ("yüksekte", "yuksekte", "iskele", "çatı", "cati", "düşme", "dusme", "emniyet kemeri")),
    ("unguarded_machine", ("koruyucusuz", "makine", "pres", "testere", "dönen aksam", "donen aksam")),
    ("chemical_spill", ("kimyasal", "dökülme", "dokulme", "asit", "solvent", "sds")),
    ("fire_hot_work", ("yangın", "yangin", "kaynak", "kıvılcım", "kivilcim", "sıcak iş", "sicak is", "alev")),
    ("confined_space", ("kapalı alan", "kapali alan", "tank", "kuyu", "kanal")),
    ("falling_object", ("düşen cisim", "dusen cisim", "üstten", "ustten", "malzeme düş")),
    ("poor_housekeeping", ("düzensiz", "duzensiz", "dağınık", "daginik", "5s", "ev düzeni")),
    ("noise_vibration", ("gürültü", "gurultu", "titreşim", "titresim", "db")),
]


def _fold(text: str) -> str:
    """Basit Türkçe/ASCII katlama — eşleşme için."""
    t = (text or "").casefold()
    # yaygın Türkçe harf eşlemeleri
    repl = (
        ("ı", "i"),
        ("İ", "i"),
        ("ş", "s"),
        ("ğ", "g"),
        ("ü", "u"),
        ("ö", "o"),
        ("ç", "c"),
    )
    for a, b in repl:
        t = t.replace(a.casefold(), b)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t


def _suggest_photo_tags(folded: str) -> list[str]:
    selected: list[str] = []
    for code, keywords in _PHOTO_TAG_RULES:
        for kw in keywords:
            fk = _fold(kw)
            if fk and fk in folded:
                selected.append(code)
                break
    return selected


def suggest_hazard_from_text(text: str, *, activity: str | None = None) -> dict[str, Any]:
    """Serbest metinden kategori + olasılık + foto etiket ipucu üret (stub/heuristik)."""
    blob = " ".join(x for x in [(text or "").strip(), (activity or "").strip()] if x)
    if not blob or len(blob) < 3:
        return {
            "engine": HINT_ENGINE,
            "matched": False,
            "suggested_category": None,
            "probability_hint": None,
            "confidence": 0.0,
            "matched_keywords": [],
            "alternatives": [],
            "suggested_photo_tags": [],
            "note": "En az birkaç kelimelik faaliyet veya risk tanımı yazın.",
        }

    folded = _fold(blob)
    photo_tags = _suggest_photo_tags(folded)
    scored: list[tuple[int, str, int, list[str]]] = []
    for category, prob_hint, keywords in _RULES:
        hits: list[str] = []
        for kw in keywords:
            fk = _fold(kw)
            if not fk:
                continue
            # kelime sınırı gevşek: substring (Türkçe birleşik ifadeler için)
            if fk in folded or re.search(rf"(?<!\w){re.escape(fk)}(?!\w)", folded):
                hits.append(kw)
        if hits:
            # daha uzun anahtarlara hafif bonus
            score = len(hits) + sum(0.25 for h in hits if len(h) >= 8)
            scored.append((int(score * 4), category, prob_hint, hits))

    if not scored:
        return {
            "engine": HINT_ENGINE,
            "matched": False,
            "suggested_category": None,
            "probability_hint": None,
            "confidence": 0.0,
            "matched_keywords": [],
            "alternatives": [],
            "suggested_photo_tags": photo_tags,
            "note": "Anahtar kelime eşleşmedi; kategoriyi kütüphaneden seçin.",
        }

    scored.sort(key=lambda x: (-x[0], x[1]))
    best_score, best_cat, best_prob, best_hits = scored[0]
    max_possible = 12.0
    confidence = round(min(0.95, best_score / max_possible), 2)
    alternatives = [
        {
            "category": cat,
            "probability_hint": prob,
            "matched_keywords": hits[:6],
            "score": sc,
        }
        for sc, cat, prob, hits in scored[1:4]
    ]
    return {
        "engine": HINT_ENGINE,
        "matched": True,
        "suggested_category": best_cat,
        "probability_hint": best_prob,
        "confidence": confidence,
        "matched_keywords": best_hits[:8],
        "alternatives": alternatives,
        "suggested_photo_tags": photo_tags,
        "note": "Öneri anahtar kelimeye dayalıdır; nihai seçim İSG uzmanına aittir.",
    }
