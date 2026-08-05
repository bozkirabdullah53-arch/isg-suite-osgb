"""Print a compact, stable summary of NACE profiles requiring risk review."""
from __future__ import annotations

import json
import re
from collections import Counter

from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_topics import sectors_list_for_api

_EXACT_NACE_RE = re.compile(r"^\d{2}(?:\.\d{2}){1,2}$")


def main() -> int:
    counts: Counter[tuple[str, str]] = Counter()
    for row in sectors_list_for_api():
        key = str(row.get("code") or "").strip()
        nace = str(row.get("nace") or "").strip()
        if not key.startswith("nace_") or not _EXACT_NACE_RE.fullmatch(nace):
            continue
        result = resolve_exact_nace(key)
        if result.classification_status == "review_required":
            counts[(
                str(result.content_profile_code or "missing"),
                str(result.content_profile_name or ""),
            )] += 1

    rows = [
        {"profile": profile, "name": name, "nace_count": count}
        for (profile, name), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0][0])
        )
    ]
    print("NACE_REVIEW_PROFILE_SUMMARY=" + json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
