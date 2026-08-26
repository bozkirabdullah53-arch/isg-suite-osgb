"""Explicit maintenance command for visual field-inspection retention.

Dry-run is the default. Use ``--execute`` only from a reviewed scheduler or
operator session; approved reports remain protected unless ``--include-approved``
is also supplied.
"""
from __future__ import annotations

import argparse

from app.core.database import SessionLocal
from app.services.field_inspection_retention import archive_expired_field_inspections


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive expired visual field inspections")
    parser.add_argument("--execute", action="store_true", help="apply reversible soft-archive")
    parser.add_argument("--include-approved", action="store_true", help="also archive approved reports")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        count = archive_expired_field_inspections(
            db,
            limit=args.limit,
            include_approved=args.include_approved,
            dry_run=not args.execute,
        )
        print(f"{'archived' if args.execute else 'eligible'}={count}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
