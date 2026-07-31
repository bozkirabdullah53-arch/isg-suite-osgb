"""Render cron: keep API warm and log health version (B-03)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("WARMUP_API_URL", "https://isg-suite-api-1u9t.onrender.com").rstrip("/")
TIMEOUT = float(os.environ.get("WARMUP_TIMEOUT_SEC", "90"))


def main() -> int:
    url = f"{API}/health"
    req = urllib.request.Request(url, headers={"User-Agent": "isg-suite-warmup/1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        print(f"warmup FAIL http={e.code} url={url}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"warmup FAIL {e!r} url={url}", file=sys.stderr)
        return 1

    version = None
    try:
        version = json.loads(body).get("version")
    except Exception:
        pass
    print(f"warmup OK http={status} version={version or '?'} url={url}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
