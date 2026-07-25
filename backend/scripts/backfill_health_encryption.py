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

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.entities import HealthRecord
from app.services.health_field_crypto import (
    SENSITIVE_TEXT_FIELDS,
    encrypt_field,
    is_encrypted,
)


def backfill(*, commit: bool) -> dict:
    if not settings.health_field_encryption_enabled:
        return {"status": "skipped", "reason": "health_field_encryption_enabled=false"}

    touched_rows = 0
    touched_fields = 0
    with SessionLocal() as db:
        rows = list(db.scalars(select(HealthRecord)).all())
        for row in rows:
            changed = False
            for field in SENSITIVE_TEXT_FIELDS:
                raw = getattr(row, field, None)
                if not raw or is_encrypted(raw):
                    continue
                setattr(row, field, encrypt_field(raw))
                touched_fields += 1
                changed = True
            if changed:
                touched_rows += 1
        if commit and touched_rows:
            db.commit()
        else:
            db.rollback()
    return {
        "status": "ok",
        "commit": commit,
        "rows_touched": touched_rows,
        "fields_touched": touched_fields,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true", help="DB'ye yaz")
    parser.add_argument("--dry-run", action="store_true", help="Yalnız say (varsayılan)")
    args = parser.parse_args()
    commit = bool(args.commit) and not bool(args.dry_run)
    result = backfill(commit=commit)
    print(result)
    return 0 if result.get("status") in ("ok", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
