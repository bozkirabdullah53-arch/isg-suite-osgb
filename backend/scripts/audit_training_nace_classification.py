"""Audit every official NACE catalog row without mutating training data."""
from __future__ import annotations

import json
import re
from collections import Counter

from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_topics import sectors_list_for_api

_EXACT_NACE_RE = re.compile(r"^\d{2}(?:\.\d{2}){1,2}$")


def _is_official_nace_row(row: dict) -> bool:
    key = str(row.get("code") or "").strip()
    nace = str(row.get("nace") or "").strip()
    return key.startswith("nace_") and bool(_EXACT_NACE_RE.fullmatch(nace))


def main() -> int:
    all_rows = list(sectors_list_for_api())
    official_rows = [row for row in all_rows if _is_official_nace_row(row)]
    non_nace_options = [
        {
            "catalog_key": str(row.get("code") or ""),
            "nace_code": str(row.get("nace") or ""),
            "description": str(row.get("name") or ""),
        }
        for row in all_rows
        if not _is_official_nace_row(row)
    ]
    statuses: Counter[str] = Counter()
    profiles: Counter[str] = Counter()
    invalid_official: list[dict[str, str]] = []
    review_required: list[dict[str, str]] = []

    for row in official_rows:
        key = str(row.get("code") or "").strip()
        try:
            result = resolve_exact_nace(key)
        except ValueError as exc:
            invalid_official.append(
                {
                    "catalog_key": key,
                    "nace_code": str(row.get("nace") or ""),
                    "description": str(row.get("name") or ""),
                    "error": str(exc),
                }
            )
            continue
        statuses[result.classification_status] += 1
        profiles[str(result.content_profile_code or "missing")] += 1
        if result.classification_status == "review_required":
            review_required.append(
                {
                    "catalog_key": str(result.catalog_key or ""),
                    "nace_code": str(result.nace_code or ""),
                    "description": str(result.nace_description or ""),
                    "content_profile": str(result.content_profile_code or ""),
                }
            )

    payload = {
        "catalog_option_count": len(all_rows),
        "official_nace_count": len(official_rows),
        "resolved_official_count": len(official_rows) - len(invalid_official),
        "invalid_official_count": len(invalid_official),
        "non_nace_option_count": len(non_nace_options),
        "non_nace_options": non_nace_options,
        "status_counts": dict(sorted(statuses.items())),
        "profile_count": len(profiles),
        "review_required_count": len(review_required),
        "review_required_sample": review_required[:50],
        "invalid_official": invalid_official,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if invalid_official else 0


if __name__ == "__main__":
    raise SystemExit(main())
