#!/usr/bin/env python3
"""Şirket profili ve kanıt defterinden hassas veri içermeyen nihai hazırlık raporu üretir."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ibys_application_evidence import assess_verified_application_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description="İBYS başvuru kanıt defteri doğrulama")
    parser.add_argument("--company-profile", required=True, type=Path)
    parser.add_argument("--evidence-ledger", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        profile = json.loads(args.company_profile.read_text(encoding="utf-8"))
        ledger = json.loads(args.evidence_ledger.read_text(encoding="utf-8"))
        if not isinstance(profile, dict) or not isinstance(ledger, dict):
            raise ValueError("profile and evidence ledger must be JSON objects")
        report = assess_verified_application_preflight(profile, ledger)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Kanıt doğrulaması başlatılamadı: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ready_for_submission": report["ready_for_submission"],
                "application_preparation_percent": report["application_preparation_percent"],
                "evidence_valid": report["evidence_validation"]["valid"],
                "output": str(args.output),
                "official_registration_claim": False,
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["ready_for_submission"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
