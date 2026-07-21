"""0.9.120 — GHS/CLP tehlike etiketi checklist (stub).

Ücretli etiket OCR yok: saha uzmanı ürün üzerinde piktogram işaretler.
"""
from __future__ import annotations

import json
from typing import Any

GHS_ENGINE = "ghs-label-checklist-v1"

# Kod → Türkçe etiket (CLP piktogramları)
GHS_PICTOGRAMS: list[dict[str, str]] = [
    {"code": "GHS01", "label": "Patlayıcı"},
    {"code": "GHS02", "label": "Alevlenir"},
    {"code": "GHS03", "label": "Oksitleyici"},
    {"code": "GHS04", "label": "Basınçlı gaz"},
    {"code": "GHS05", "label": "Aşındırıcı"},
    {"code": "GHS06", "label": "Zehirli"},
    {"code": "GHS07", "label": "Zararlı / tahriş edici"},
    {"code": "GHS08", "label": "Sağlık tehlikesi"},
    {"code": "GHS09", "label": "Çevreye zararlı"},
]

_ALLOWED = {p["code"] for p in GHS_PICTOGRAMS}


def catalog() -> list[dict[str, str]]:
    return list(GHS_PICTOGRAMS)


def parse_checklist(raw: str | None) -> dict[str, Any]:
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
    # sıralı ve tekil
    ordered = [p["code"] for p in GHS_PICTOGRAMS if p["code"] in selected]
    return {
        "engine": GHS_ENGINE,
        "selected": ordered,
        "count": len(ordered),
        "items": [
            {**p, "checked": p["code"] in ordered}
            for p in GHS_PICTOGRAMS
        ],
    }


def serialize_selected(codes: list[str] | None) -> str:
    cleaned = []
    seen: set[str] = set()
    for c in codes or []:
        code = str(c).strip().upper()
        if code in _ALLOWED and code not in seen:
            seen.add(code)
            cleaned.append(code)
    return json.dumps({"selected": cleaned}, ensure_ascii=False)
