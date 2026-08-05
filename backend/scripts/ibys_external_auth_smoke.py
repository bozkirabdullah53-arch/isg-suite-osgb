#!/usr/bin/env python3
"""Staging/production İBYS başvuru rotaları için anonim dış smoke kanıtı üretir."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ibys_external_auth_smoke import run_external_auth_smoke


def main() -> int:
    parser = argparse.ArgumentParser(description="İBYS anonim dış yetkilendirme smoke testi")
    parser.add_argument("--base-url", required=True, help="Örn. https://isg-suite-api-staging.onrender.com")
    parser.add_argument("--output", required=True, type=Path, help="Kanıt JSON dosyası")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--allow-http-localhost", action="store_true")
    args = parser.parse_args()

    try:
        evidence = run_external_auth_smoke(
            args.base_url,
            timeout_s=args.timeout,
            allow_http_localhost=args.allow_http_localhost,
        )
    except ValueError as exc:
        print(f"Smoke testi başlatılamadı: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": evidence["overall_ok"],
                "output": str(args.output),
                "evidence_sha256": evidence["evidence_sha256"],
                "check_count": len(evidence["checks"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if evidence["overall_ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
