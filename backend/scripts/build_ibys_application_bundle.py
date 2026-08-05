#!/usr/bin/env python3
"""İmzaya hazır İBYS başvuru ZIP'i üretir; eksik bilgi/belgede fail-closed durur."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ibys_application_bundle import build_application_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="İBYS entegratör başvuru paketi üret")
    parser.add_argument("--company-profile", required=True, type=Path)
    parser.add_argument("--attachments-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        profile = json.loads(args.company_profile.read_text(encoding="utf-8"))
        data, manifest = build_application_bundle(
            profile,
            attachments_dir=args.attachments_dir,
            require_attachments=True,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Başvuru paketi üretilemedi: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(args.output),
                "file_count": len(manifest["files"]),
                "bundle_version": manifest["bundle_version"],
                "official_registration_claim": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
