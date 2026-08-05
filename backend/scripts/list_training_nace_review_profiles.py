"""Print a stable summary of NACE profiles requiring risk review."""
from __future__ import annotations

import json
import re
from collections import defaultdict

from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_topics import sectors_list_for_api

_EXACT_NACE_RE = re.compile(r"^\d{2}(?:\.\d{2}){1,2}$")


def main() -> int:
    profiles: dict[str, dict] = defaultdict(
        lambda: {
            "name": "",
            "nace_count": 0,
            "training_topics": [],
            "sample_nace": [],
        }
    )
    for row in sectors_list_for_api():
        key = str(row.get("code") or "").strip()
        nace = str(row.get("nace") or "").strip()
        if not key.startswith("nace_") or not _EXACT_NACE_RE.fullmatch(nace):
            continue
        result = resolve_exact_nace(key)
        if result.classification_status != "review_required":
            continue
        profile = str(result.content_profile_code or "missing")
        item = profiles[profile]
        item["name"] = str(result.content_profile_name or "")
        item["nace_count"] += 1
        item["training_topics"] = list(result.training_topics)
        if len(item["sample_nace"]) < 3:
            item["sample_nace"].append(
                {
                    "nace_code": str(result.nace_code or ""),
                    "description": str(result.nace_description or ""),
                }
            )

    rows = [
        {"profile": profile, **details}
        for profile, details in sorted(
            profiles.items(),
            key=lambda item: (-int(item[1]["nace_count"]), item[0]),
        )
    ]
    print(
        "NACE_REVIEW_PROFILE_SUMMARY="
        + json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
