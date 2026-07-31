"""One-off rewrite: replace _SECTOR_RAW inline list with JSON loader."""
from __future__ import annotations

from pathlib import Path
import re

TARGET = Path(__file__).resolve().parent.parent / "app" / "services" / "training_topics.py"

NEW_LOADER = '''
def _load_sector_raw() -> list[tuple[str, str, str, list[str]]]:
    path = Path(__file__).resolve().parent / "data" / "nace_sectors.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    out: list[tuple[str, str, str, list[str]]] = []
    for row in rows:
        out.append(
            (
                str(row["code"]),
                str(row["name"]),
                str(row["hazard_class"]),
                list(row.get("topics") or []),
            )
        )
    if not out:
        raise RuntimeError(f"NACE sektör kataloğu boş: {path}")
    return out


# NACE 2026 resmi tehlike sınıfları (CSV → nace_sectors.json)
_SECTOR_RAW: list[tuple[str, str, str, list[str]]] = _load_sector_raw()
'''

NEW_SEKTOR_KODU = '''def sektor_kodu_cozumle(sektor: str | None) -> str:
    if not sektor:
        return "genel_uretim"
    raw = sektor.strip()
    if raw in SEKTOREL_EGITIM_KONULARI:
        return raw
    nace_code = "nace_" + raw.replace(".", "_")
    if nace_code in SEKTOREL_EGITIM_KONULARI:
        return nace_code
    for kod, ad in SEKTOR_SECENEKLERI:
        if ad.casefold() == raw.casefold():
            return kod
    if raw in ("01", "02", "03", "04", "05"):
        return "genel_uretim"
    return "genel_uretim"
'''

NEW_SECTORS_API = '''def sectors_list_for_api() -> list[dict]:
    path = Path(__file__).resolve().parent / "data" / "nace_sectors.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for row in sorted(rows, key=lambda x: str(x.get("label") or x.get("name") or "").casefold()):
        topics = [sure_ekini_temizle(t) for t in (row.get("topics") or [])]
        items.append({
            "code": row["code"],
            "name": row["name"],
            "label": row.get("label") or f"{row.get('nace','')} / {row['name']} / {row['hazard_class']}",
            "hazard_class": row["hazard_class"],
            "nace": row.get("nace"),
            "topics": topics,
        })
    return items
'''


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    start = text.index("_SECTOR_RAW")
    assign = text.index("= [", start)
    idx = assign + 2
    depth = 0
    list_end = None
    for i in range(idx, len(text)):
        c = text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                list_end = i + 1
                break
    if list_end is None:
        raise RuntimeError("Could not find end of _SECTOR_RAW list")
    # Drop old header comments immediately before _SECTOR_RAW if present
    block_start = start
    prev = text.rfind("\n", 0, start)
    while prev >= 0:
        line = text[prev + 1 : start].strip()
        if line.startswith("#") and "SECTOR" not in line and "_SECTOR" not in line:
            block_start = prev + 1
            prev2 = text.rfind("\n", 0, prev)
            if prev2 < 0:
                break
            start_line = text[prev2 + 1 : prev].strip()
            if start_line.startswith("#"):
                block_start = prev2 + 1
                prev = text.rfind("\n", 0, prev2)
                continue
            break
        break

    text = text[:block_start] + NEW_LOADER.lstrip("\n") + text[list_end:]

    # Top-level imports
    if "import json\n" not in text:
        text = text.replace("import re\n", "import json\nimport re\n", 1)
    if "from pathlib import Path\n" not in text:
        text = text.replace("import json\n", "import json\nfrom pathlib import Path\n", 1)

    # Replace sektor_kodu_cozumle
    m = re.search(
        r"def sektor_kodu_cozumle\(sektor: str \| None\) -> str:\n(?:    .+\n)+?(?=\n\ndef )",
        text,
    )
    if not m:
        raise RuntimeError("sektor_kodu_cozumle not found")
    text = text[: m.start()] + NEW_SEKTOR_KODU + text[m.end() :]

    # Replace sectors_list_for_api
    m2 = re.search(
        r"def sectors_list_for_api\(\) -> list\[dict\]:\n(?:    .+\n)+?(?=\n\ndef )",
        text,
    )
    if not m2:
        raise RuntimeError("sectors_list_for_api not found")
    text = text[: m2.start()] + NEW_SECTORS_API + text[m2.end() :]

    TARGET.write_text(text, encoding="utf-8")
    print("Wrote", TARGET, "lines", len(text.splitlines()))


if __name__ == "__main__":
    main()

