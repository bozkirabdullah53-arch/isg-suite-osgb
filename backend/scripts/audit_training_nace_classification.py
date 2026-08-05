"""Audit every catalog row without mutating training data."""
from __future__ import annotations

import json
from collections import Counter

from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_topics import sectors_list_for_api


def main() -> int:
    rows = sectors_list_for_api()
    statuses: Counter[str] = Counter()
    profiles: Counter[str] = Counter()
    invalid: list[dict[str, str]] = []
    review_required: list[dict[str, str]] = []

    for row in rows:
        key = str(row.get("code") or "").strip()
        try:
            result = resolve_exact_nace(key)
        except ValueError as exc:
            invalid.append(
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
        "catalog_count": len(rows),
        "resolved_count": len(rows) - len(invalid),
        "invalid_count": len(invalid),
        "status_counts": dict(sorted(statuses.items())),
        "profile_count": len(profiles),
        "review_required_count": len(review_required),
        "review_required_sample": review_required[:50],
        "invalid": invalid,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
