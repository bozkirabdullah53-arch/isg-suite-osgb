# -*- coding: utf-8 -*-
"""Generate training sector JSON from official NACE hazard-class CSV."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = BACKEND_ROOT / "data" / "guncel_nace_tehlike_siniflari_2026.csv"
OUT_PATHS = [
    BACKEND_ROOT / "app" / "services" / "data" / "nace_sectors.json",
    BACKEND_ROOT.parent / "frontend" / "public" / "training-sectors.json",
]

DEFAULT_TOPICS = [
    "Makine ve ekipmanlarla güvenli çalışma",
    "İşyeri içi araç-yaya trafiği ve kör noktalar",
    "Elle taşıma, ergonomi ve güvenli istifleme",
    "Yangın, acil durum ve tahliye uygulamaları",
    "KKD kullanımı, bakım güvenliği ve işyeri düzeni",
]

COL_NACE = "NACE Altılı Kod"
COL_NAME = "Faaliyet Tanımı"
COL_HAZARD = "Tehlike Sınıfı"
COL_SECTION = "Kesit Kodu"
COL_SECTOR = "Ana Sektör"
COL_STATUS = "Durum"

HAZARD_CANONICAL = ("Az Tehlikeli", "Tehlikeli", "Çok Tehlikeli")


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_hazard(raw: str) -> str | None:
    s = _collapse_ws(raw or "")
    if not s:
        return None
    lower = s.casefold()
    if "cok" in lower.replace("ç", "c") or "çok" in lower:
        if "tehlikeli" in lower:
            return "Çok Tehlikeli"
    if lower.startswith("az") and "tehlikeli" in lower:
        return "Az Tehlikeli"
    if "tehlikeli" in lower:
        return "Tehlikeli"
    for canonical in HAZARD_CANONICAL:
        if s == canonical:
            return canonical
    return None


def nace_to_code(nace: str) -> str:
    return "nace_" + nace.replace(".", "_")


def load_sectors() -> list[dict]:
    if not CSV_PATH.is_file():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    seen_nace: set[str] = set()
    items: list[dict] = []

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            status = (row.get(COL_STATUS) or "").strip()
            if status and status.casefold() != "aktif":
                continue

            nace = _collapse_ws(row.get(COL_NACE) or "")
            if not nace:
                continue
            if nace in seen_nace:
                continue
            seen_nace.add(nace)

            name = _collapse_ws(row.get(COL_NAME) or "")
            hazard = normalize_hazard(row.get(COL_HAZARD) or "")
            if hazard is None:
                print(f"WARN: skip NACE {nace}: unknown hazard {row.get(COL_HAZARD)!r}", file=sys.stderr)
                continue

            section = _collapse_ws(row.get(COL_SECTION) or "") or None
            entry: dict = {
                "code": nace_to_code(nace),
                "name": name,
                "label": f"{nace} / {name} / {hazard}",
                "hazard_class": hazard,
                "nace": nace,
                "topics": list(DEFAULT_TOPICS),
            }
            if section:
                entry["section"] = section
            items.append(entry)

    legacy = {
        "code": "genel_uretim",
        "name": "Genel Fabrika ve Üretim",
        "label": "genel / Genel Fabrika ve Üretim / Tehlikeli",
        "hazard_class": "Tehlikeli",
        "nace": None,
        "topics": list(DEFAULT_TOPICS),
    }
    items.append(legacy)
    return items


def write_json(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main() -> None:
    data = load_sectors()
    for out in OUT_PATHS:
        write_json(out, data)
    print(len(data))
    if len(data) >= 2:
        print(data[0]["label"])
        print(data[1]["label"])
    print(data[-1]["label"])


if __name__ == "__main__":
    main()

