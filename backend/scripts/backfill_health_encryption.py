"""Mevcut düz metin sağlık alanlarını şifrele (P0-07 backfill).

Flag kapalıysa çıkış. Zaten enc:v1: olanlar atlanır.

  python -m scripts.backfill_health_encryption --dry-run
  python -m scripts.backfill_health_encryption --commit
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal
from app.services.health_field_crypto import backfill_plaintext_records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true", help="DB'ye yaz")
    parser.add_argument("--dry-run", action="store_true", help="Yalnız say (varsayılan)")
    args = parser.parse_args()
    commit = bool(args.commit) and not bool(args.dry_run)
    with SessionLocal() as db:
        result = backfill_plaintext_records(db, commit=commit)
    print(result)
    return 0 if result.get("status") in ("ok", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
