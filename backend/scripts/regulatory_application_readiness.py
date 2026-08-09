#!/usr/bin/env python3
"""Print an application-readiness evidence snapshot without changing data."""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.services.regulatory_application_readiness import build_regulatory_application_readiness
from app.services.regulatory_data_preflight import build_regulatory_data_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description="İBYS + İSBS/e-Reçete application readiness")
    parser.add_argument("--osgb-id", type=int, default=None)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when code-level readiness fails or high-priority local data findings exist.",
    )
    args = parser.parse_args()

    report = build_regulatory_application_readiness()
    with SessionLocal() as db:
        report["data_preflight"] = build_regulatory_data_preflight(db, osgb_id=args.osgb_id)

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if not args.strict:
        return 0
    if not report["summary"]["code_application_layer_ready"]:
        return 2
    if report["data_preflight"]["high_priority_findings"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
