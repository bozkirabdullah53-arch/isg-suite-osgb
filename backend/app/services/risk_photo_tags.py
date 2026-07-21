"""0.9.121 — Risk fotoğrafı tehlike etiketi checklist (stub).

Ücretli görüntü AI yok: saha uzmanı medya yüklerken isteğe bağlı etiket seçer.
"""
from __future__ import annotations

import json
from typing import Any

TAGS_ENGINE = "checklist-v1"

# Kod → Türkçe etiket (saha gözlem checklist)
PHOTO_TAGS: list[dict[str, str]] = [
    {"code": "ppe_missing", "label": "PPE / KKD eksik"},
    {"code": "slippery_floor", "label": "Kaygan zemin"},
    {"code": "electrical", "label": "Elektrik"},
    {"code": "work_at_height", "label": "Yüksekte çalışma"},
    {"code": "unguarded_machine", "label": "Koruyucusuz makine"},
    {"code": "chemical_spill", "label": "Kimyasal dökülme"},
    {"code": "fire_hot_work", "label": "Yangın / sıcak iş"},
    {"code": "confined_space", "label": "Kapalı alan"},
    {"code": "falling_object", "label": "Düşen cisim"},
    {"code": "poor_housekeeping", "label": "Düzensiz alan"},
    {"code": "noise_vibration", "label": "Gürültü / titreşim"},
    {"code": "other", "label": "Diğer"},
]

_ALLOWED = {p["code"] for p in PHOTO_TAGS}
_LABEL = {p["code"]: p["label"] for p in PHOTO_TAGS}


def catalog() -> list[dict[str, str]]:
    return list(PHOTO_TAGS)


def parse_tags(raw: str | None) -> dict[str, Any]:
    selected: list[str] = []
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                selected = [c for c in (data.get("selected") or []) if c in _ALLOWED]
            elif isinstance(data, list):
                selected = [c for c in data if c in _ALLOWED]
        except (TypeError, json.JSONDecodeError):
            selected = []
    ordered = [p["code"] for p in PHOTO_TAGS if p["code"] in selected]
    return {
        "engine": TAGS_ENGINE,
        "selected": ordered,
        "labels": [_LABEL[c] for c in ordered],
        "count": len(ordered),
        "items": [{**p, "checked": p["code"] in ordered} for p in PHOTO_TAGS],
    }


def serialize_selected(codes: list[str] | None) -> str | None:
    cleaned: list[str] = []
    seen: set[str] = set()
    for c in codes or []:
        code = str(c).strip().lower()
        if code in _ALLOWED and code not in seen:
            seen.add(code)
            cleaned.append(code)
    if not cleaned:
        return None
    return json.dumps({"selected": cleaned}, ensure_ascii=False)


def parse_form_tags(raw: str | None) -> list[str]:
    """Upload Form alanı: JSON dizi, {"selected":[...]} veya virgüllü kodlar."""
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return [
                c
                for c in (data.get("selected") or [])
                if str(c).strip().lower() in _ALLOWED
            ]
        if isinstance(data, list):
            return [
                str(c).strip().lower()
                for c in data
                if str(c).strip().lower() in _ALLOWED
            ]
    except (TypeError, json.JSONDecodeError):
        pass
    return [p for p in (x.strip().lower() for x in text.split(",")) if p in _ALLOWED]
