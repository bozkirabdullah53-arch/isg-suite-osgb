from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings


def backup_sqlite(database_url: str, target: Path) -> None:
    source = Path(database_url.removeprefix("sqlite:///")).resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {source}")
    shutil.copy2(source, target.with_suffix(".db"))


def backup_postgresql(database_url: str, target: Path) -> None:
    parsed = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://"))
    output = target.with_suffix(".dump")
    command = [
        "pg_dump",
        "--format=custom",
        "--file", str(output),
        database_url.replace("postgresql+psycopg://", "postgresql://"),
    ]
    subprocess.run(command, check=True)


def main() -> None:
    backup_dir = Path(settings.backup_dir).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"isgsuite-{stamp}"

    if settings.database_url.startswith("sqlite"):
        backup_sqlite(settings.database_url, target)
        produced = target.with_suffix(".db")
    elif settings.database_url.startswith(("postgresql", "postgres")):
        backup_postgresql(settings.database_url, target)
        produced = target.with_suffix(".dump")
    else:
        raise RuntimeError("Unsupported database type for backup.")

    key = (settings.backup_encryption_key or "").strip()
    if key and produced.exists():
        import base64
        import hashlib
        from cryptography.fernet import Fernet

        digest = hashlib.sha256(key.encode("utf-8")).digest()
        enc = produced.with_suffix(produced.suffix + ".enc")
        enc.write_bytes(Fernet(base64.urlsafe_b64encode(digest)).encrypt(produced.read_bytes()))
        produced.unlink(missing_ok=True)
        produced = enc

    print(f"Backup completed: {produced}")


if __name__ == "__main__":
    main()
