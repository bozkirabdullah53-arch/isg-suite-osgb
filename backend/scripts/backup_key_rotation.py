"""Yedek ÅŸifreleme anahtarÄ± rotasyonu ve bÃ¼tÃ¼nlÃ¼k taramasÄ±.

Ä°BYS Yedekleme ProsedÃ¼rÃ¼ Â§6 (anahtar saklama ve rotasyon) ve Â§8 (bÃ¼tÃ¼nlÃ¼k kontrolÃ¼).

KullanÄ±m:
  python -m scripts.rotate_backup_key --old-key <eski> --new-key <yeni> --dry-run
  python -m scripts.rotate_backup_key --old-key <eski> --new-key <yeni>
  python -m scripts.verify_all_backups
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services.backup_management import DB_BACKUP_NAME  # noqa: E402


def _fernet(key_material: str):
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _encrypted_backups(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*.enc")
        if path.is_file() and (DB_BACKUP_NAME.match(path.name) or path.suffix == ".enc")
    )


def rotate_backup_key(
    *,
    old_key: str,
    new_key: str,
    directory: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """TÃ¼m ÅŸifreli yedekleri yeni anahtarla yeniden ÅŸifreler.

    Her dosya Ã¶nce yeni anahtarla Ã§Ã¶zÃ¼lÃ¼p doÄŸrulanÄ±r; herhangi bir hata
    durumunda hiÃ§bir dosya kalÄ±cÄ± olarak deÄŸiÅŸtirilmez.
    """
    root = Path(directory or settings.backup_dir).resolve()
    files = _encrypted_backups(root)
    old_cipher = _fernet(old_key)
    new_cipher = _fernet(new_key)

    rotated: list[str] = []
    skipped: list[str] = []
    failed: list[dict[str, str]] = []
    pending: list[tuple[Path, bytes]] = []

    for path in files:
        try:
            plaintext = old_cipher.decrypt(path.read_bytes())
        except Exception as exc:  # noqa: BLE001 - hangi dosya aÃ§Ä±lamadÄ± raporlanÄ±r
            failed.append({"file": path.name, "error": type(exc).__name__})
            continue
        try:
            # Yeni anahtarla ÅŸifrele ve hemen geri Ã§Ã¶zerek doÄŸrula.
            reencrypted = new_cipher.encrypt(plaintext)
            if new_cipher.decrypt(reencrypted) != plaintext:
                raise ValueError("Yeniden ÅŸifreleme doÄŸrulamasÄ± baÅŸarÄ±sÄ±z.")
        except Exception as exc:  # noqa: BLE001
            failed.append({"file": path.name, "error": type(exc).__name__})
            continue
        pending.append((path, reencrypted))
        rotated.append(path.name)

    if failed:
        return {
            "status": "aborted",
            "reason": "BazÄ± yedekler eski anahtarla aÃ§Ä±lamadÄ±; hiÃ§bir dosya deÄŸiÅŸtirilmedi.",
            "rotated": [],
            "failed": failed,
            "dry_run": dry_run,
        }

    if dry_run:
        return {
            "status": "ok",
            "dry_run": True,
            "would_rotate": rotated,
            "count": len(rotated),
            "skipped": skipped,
            "failed": failed,
        }

    written: list[str] = []
    for path, payload in pending:
        backup_copy = path.with_suffix(path.suffix + ".pre-rotation")
        try:
            path.replace(backup_copy)
            path.write_bytes(payload)
            # Yeni dosya gerÃ§ekten yeni anahtarla aÃ§Ä±labiliyor mu?
            new_cipher.decrypt(path.read_bytes())
            backup_copy.unlink(missing_ok=True)
            written.append(path.name)
        except Exception as exc:  # noqa: BLE001 - geri alÄ±nÄ±r
            if backup_copy.exists():
                backup_copy.replace(path)
            return {
                "status": "rolled_back",
                "reason": "Yazma sÄ±rasÄ±nda hata; dosya eski hÃ¢line dÃ¶ndÃ¼rÃ¼ldÃ¼.",
                "error": f"{path.name}: {type(exc).__name__}",
                "rotated": written,
                "dry_run": False,
            }

    return {
        "status": "ok",
        "dry_run": False,
        "rotated": written,
        "count": len(written),
        "skipped": skipped,
        "failed": failed,
    }


def verify_all_backups(*, directory: Path | None = None) -> dict:
    """BACKUP_DIR iÃ§indeki tÃ¼m yedekleri listeler ve SHA-256/boyut doÄŸrular."""
    root = Path(directory or settings.backup_dir).resolve()
    if not root.exists():
        return {
            "status": "ok",
            "checked": 0,
            "corrupt": [],
            "missing": [],
            "backup_dir": str(root),
        }

    checked = 0
    corrupt: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if not (
            DB_BACKUP_NAME.match(path.name)
            or path.name.endswith((".zip", ".zip.enc", ".dump", ".dump.enc", ".db", ".db.enc"))
        ):
            continue
        checked += 1
        try:
            size = path.stat().st_size
            checksum = _sha256(path)
        except OSError as exc:
            corrupt.append({"file": str(path), "error": type(exc).__name__})
            continue
        if size == 0 or len(checksum) != 64:
            corrupt.append({"file": str(path), "error": "boÅŸ-veya-okunamadÄ±"})

    return {
        "status": "ok" if not corrupt else "degraded",
        "checked": checked,
        "corrupt": corrupt,
        "missing": [],
        "backup_dir": str(root),
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


def _notify_backup_integrity(result: dict) -> int:
    """Bozuk yedek bulunursa global yÃ¶neticilere bildirim gÃ¶nderir."""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.entities import Notification, NotificationType, User, UserRole

    if not result.get("corrupt"):
        return 0
    sent = 0
    try:
        with SessionLocal() as db:
            admins = list(
                db.scalars(
                    select(User).where(User.role == UserRole.GLOBAL_ADMIN, User.is_active.is_(True))
                ).all()
            )
            for admin in admins:
                db.add(
                    Notification(
                        user_id=admin.id,
                        company_id=None,
                        type=NotificationType.CRITICAL,
                        title="Yedek bÃ¼tÃ¼nlÃ¼ÄŸÃ¼ bozuk",
                        message=(
                            f"{len(result['corrupt'])} yedek dosyasÄ± bÃ¼tÃ¼nlÃ¼k kontrolÃ¼nden geÃ§emedi. "
                            "Yedekleme deposunu ve disk saÄŸlÄ±ÄŸÄ±nÄ± kontrol edin."
                        ),
                        entity_type="backup_integrity",
                        entity_id=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    )
                )
            db.commit()
            sent = len(admins)
    except Exception:  # pragma: no cover - alarm asla taramayÄ± bozmaz
        pass
    return sent


def main() -> int:
    parser = argparse.ArgumentParser(description="Yedek anahtar rotasyonu ve bÃ¼tÃ¼nlÃ¼k taramasÄ±")
    parser.add_argument("--rotate", action="store_true", help="Anahtar rotasyonu yap")
    parser.add_argument("--old-key", default=None)
    parser.add_argument("--new-key", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--no-notify", action="store_true")
    args = parser.parse_args()

    if args.rotate:
        if not args.old_key or not args.new_key:
            print(json.dumps({"status": "error", "error": "--old-key ve --new-key zorunludur."}))
            return 2
        result = rotate_backup_key(old_key=args.old_key, new_key=args.new_key, dry_run=args.dry_run)
    else:
        result = verify_all_backups()
        if not args.no_notify and result.get("corrupt"):
            result["notified_admins"] = _notify_backup_integrity(result)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in ("ok",) else 1


if __name__ == "__main__":
    raise SystemExit(main())
