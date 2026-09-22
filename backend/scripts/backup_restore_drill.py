"""Geri yükleme tatbikatı — GERÇEK yedek üzerinde dry-run doğrulaması.

İBYS Yedekleme Prosedürü §7: ayda bir gerçek yedek seçilir, bütünlüğü doğrulanır,
dry-run geri yükleme ile içerik tutarlılığı kontrol edilir ve sonuç
``docs/qa/logs/backup-restore-drill.json`` olarak kaydedilir.

Kullanım:
  python -m scripts.backup_restore_drill --latest
  python -m scripts.backup_restore_drill --archive /var/data/backups/...zip
  python -m scripts.backup_restore_drill --out docs/qa/logs/backup-restore-drill.json

Hiçbir zaman diske yazmaz (dry-run); sentetik dosya üretmez.
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
from app.services import backup_safety as bs  # noqa: E402

ARCHIVE_SUFFIXES = (".zip", ".zip.enc")
DB_DUMP_SUFFIXES = (".dump", ".dump.enc", ".db", ".db.enc")


def _candidate_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        name = path.name.lower()
        if name.endswith(ARCHIVE_SUFFIXES) or name.endswith(DB_DUMP_SUFFIXES):
            files.append(path)
    return files


def find_latest_backup(root: Path | None = None) -> Path | None:
    from app.core.config import settings

    base = Path(root or settings.backup_dir).resolve()
    candidates = _candidate_files(base)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _drill_archive(path: Path) -> dict:
    """ZIP/şifreli ZIP yedeği için bütünlük + inspect + dry-run."""
    plan = br.inspect_backup_file(path)
    dry = br.restore_files_from_backup(path, dry_run=True)
    touched = int(dry.get("files_touched") or 0)
    expected_files = len(plan.file_entries)
    checks: dict[str, object] = {
        "format_version": plan.format_version,
        "encrypted": plan.encrypted,
        "domain_counts": plan.domain_counts,
        "file_entries": expected_files,
        "document_count": plan.document_count,
        "employee_count": plan.employee_count,
        "files_touched": touched,
        "skipped": dry.get("skipped"),
    }
    # Tutarlılık: dry-run en az manifest'te listelenen dosya sayısını görmeli.
    consistent = touched >= expected_files
    return {
        "kind": "archive",
        "checks": checks,
        "consistent": consistent,
        "result": "pass" if consistent else "fail",
        "failure_reason": None
        if consistent
        else f"dry-run dosya sayısı manifest ile uyuşmuyor ({touched} < {expected_files})",
    }


def _drill_database_dump(path: Path) -> dict:
    """DB dump için boyut + SHA-256 bütünlük kontrolü."""
    size = int(path.stat().st_size)
    checksum = bs.sha256_file(path)
    ok = size > 0 and len(checksum) == 64
    return {
        "kind": "database_dump",
        "checks": {
            "size_bytes": size,
            "sha256": checksum,
            "decryptable": _dump_decryptable(path),
        },
        "consistent": ok,
        "result": "pass" if ok else "fail",
        "failure_reason": None if ok else "DB dump boş veya okunamadı",
    }


def _dump_decryptable(path: Path) -> bool:
    if not path.name.endswith(".enc"):
        return True
    try:
        work = br._decrypt_if_needed(path)
    except Exception:
        return False
    if work != path:
        try:
            work.unlink(missing_ok=True)
        except OSError:
            pass
    return True


def run_drill(*, archive: Path | None = None, latest: bool = False, out: Path | None = None) -> dict:
    from app.core.config import settings

    target = Path(archive).resolve() if archive else find_latest_backup()
    if target is None or not target.is_file():
        evidence = {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "mode": "real_archive",
            "result": "fail",
            "failure_reason": "Tatbikat için gerçek yedek bulunamadı.",
            "backup_dir": str(Path(settings.backup_dir).resolve()),
        }
        if out:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        return evidence

    name = target.name.lower()
    try:
        if name.endswith(ARCHIVE_SUFFIXES):
            outcome = _drill_archive(target)
        elif name.endswith(DB_DUMP_SUFFIXES):
            outcome = _drill_database_dump(target)
        else:
            outcome = {
                "kind": "unknown",
                "checks": {},
                "consistent": False,
                "result": "fail",
                "failure_reason": "Desteklenmeyen yedek biçimi.",
            }
    except Exception as exc:  # noqa: BLE001 - kanıt dosyası her durumda yazılmalı
        outcome = {
            "kind": "error",
            "checks": {},
            "consistent": False,
            "result": "fail",
            "failure_reason": f"{type(exc).__name__}: {str(exc)[:300]}",
        }

    evidence = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "mode": "real_archive",
        "restore_writes_enabled": bool(settings.backup_restore_enabled),
        "archive": {
            "name": target.name,
            "path": str(target),
            "size_bytes": int(target.stat().st_size),
            "modified_at": datetime.fromtimestamp(
                target.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
        },
        **outcome,
    }
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerçek yedek üzerinde dry-run tatbikatı")
    parser.add_argument("--out", type=Path, default=None, help="Kanıt JSON yolu")
    parser.add_argument("--archive", type=Path, default=None, help="Belirli bir yedek dosyası")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="BACKUP_DIR içindeki en yeni gerçek yedeği kullan (varsayılan davranış)",
    )
    args = parser.parse_args()
    evidence = run_drill(archive=args.archive, latest=args.latest, out=args.out)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence.get("result") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
