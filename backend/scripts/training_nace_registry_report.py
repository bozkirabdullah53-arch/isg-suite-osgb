#!/usr/bin/env python3
"""Generate a deterministic, non-PII NACE classification evidence report."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from app.services.training_nace_registry import build_registry, registry_content_hash


def build_evidence() -> dict:
    rows = build_registry()
    status_counts = Counter(row.mapping_status for row in rows)
    hazard_counts = Counter(row.hazard_class for row in rows)
    profile_statuses: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        profile_statuses[row.profile_code][row.mapping_status] += 1

    profiles = []
    for profile, counts in sorted(profile_statuses.items()):
        profiles.append({
            "profile_code": profile,
            "entry_count": sum(counts.values()),
            "status_counts": dict(sorted(counts.items())),
        })

    return {
        "schema": "training-nace-registry-evidence-v1",
        "content_hash": registry_content_hash(rows),
        "entry_count": len(rows),
        "unique_nace_count": len({row.nace_code for row in rows}),
        "status_counts": dict(sorted(status_counts.items())),
        "hazard_counts": dict(sorted(hazard_counts.items())),
        "all_compliant": False,
        "profiles": profiles,
        "review_required": [
            {
                "nace_code": row.nace_code,
                "description": row.description,
                "profile_code": row.profile_code,
                "errors": list(row.validation_errors),
            }
            for row in rows
            if row.mapping_status == "review_required"
        ],
        "blocked": [
            {
                "nace_code": row.nace_code,
                "description": row.description,
                "profile_code": row.profile_code,
                "errors": list(row.validation_errors),
            }
            for row in rows
            if row.mapping_status == "blocked"
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_evidence()
    if report["entry_count"] != 2141 or report["unique_nace_count"] != 2141:
        raise SystemExit("NACE catalog count/uniqueness gate failed")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "entry_count": report["entry_count"],
        "content_hash": report["content_hash"],
        "status_counts": report["status_counts"],
        "blocked_count": len(report["blocked"]),
        "review_required_count": len(report["review_required"]),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
