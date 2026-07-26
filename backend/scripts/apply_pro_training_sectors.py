# -*- coding: utf-8 -*-
"""Replace Suite _SECTOR_RAW with Pro 2026 full catalog (additive, keeps API shape)."""
from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TOPICS = BACKEND / "app" / "services" / "training_topics.py"
RAW = BACKEND / "app" / "services" / "_generated_sector_raw.py"


def main() -> None:
    text = TOPICS.read_text(encoding="utf-8")
    raw = RAW.read_text(encoding="utf-8").strip() + "\n"
    start = text.index("# (kod, ad, tehlike_sinifi, 5 sektörel konu)")
    end = text.index("\ndef _topics_with_dk")
    marker = (
        "# (kod, ad, tehlike_sinifi, 5 sektörel konu) — ISG Pro 2026 tam katalog aktarımı\n"
        "# Kaynak: training_sector_catalog.py / Pro egitim/sector_catalog.py\n"
    )
    text2 = text[:start] + marker + raw + text[end:]
    TOPICS.write_text(text2, encoding="utf-8")
    print("ok", TOPICS, "sectors_lines", raw.count("\n"))


if __name__ == "__main__":
    main()
