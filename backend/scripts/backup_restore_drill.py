"""Staging backup restore drill (P0-08) — dry-run only, no disk writes.

Usage:
  python -m scripts.backup_restore_drill
  python -m scripts.backup_restore_drill --out docs/qa/logs/backup-restore-drill.json
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import backup_restore as br  # noqa: E402


def _fixture_zip(tmp: Path) -> Path:
    zpath = tmp / "drill-tenant.zip"
    manifest = {
        "format_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "osgb_id": 99,
        "osgb_name": "Drill OSGB",
        "companies": [{"id": 1, "name": "Drill Co"}],
        "document_count": 1,
        "employee_count": 1,
    }
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("files/1/docs/a.pdf", b"%PDF-1.4 drill")
        zf.writestr("osgb_files/visits/v.pdf", b"%PDF-1.4 visit")
    return zpath


def run_drill(*, out: Path | None = None) -> dict:
    import tempfile

    from app.core.config import settings

    with tempfile.TemporaryDirectory() as td:
        zpath = _fixture_zip(Path(td))
        plan = br.inspect_backup_file(zpath)
        dry = br.restore_files_from_backup(zpath, dry_run=True)
        touched = int(dry.get("files_touched") or 0)
        evidence = {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "mode": "dry_run",
            "restore_writes_enabled": bool(settings.backup_restore_enabled),
            "inspect": {
                "osgb_id": plan.osgb_id,
                "document_count": plan.document_count,
                "employee_count": plan.employee_count,
                "file_entries": len(plan.file_entries),
                "encrypted": plan.encrypted,
            },
            "dry_run": {
                "files_touched": touched,
                "skipped": dry.get("skipped"),
            },
            "result": "pass" if touched >= 1 else "fail",
        }
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup restore dry-run drill")
    parser.add_argument("--out", type=Path, default=None, help="Evidence JSON path")
    args = parser.parse_args()
    evidence = run_drill(out=args.out)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence.get("result") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
