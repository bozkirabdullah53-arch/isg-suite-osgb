from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse

from app.core.config import settings


def backup_sqlite(database_url: str, target: Path) -> None:
    source = Path(database_url.removeprefix("sqlite:///")).resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {source}")
    shutil.copy2(source, target.with_suffix(".db"))


def backup_postgresql(database_url: str, target: Path) -> None:
    parsed = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://"))
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    password = unquote(parsed.password or "") or next(
        (unquote(value) for key, value in query_items if key.casefold() == "password"),
        "",
    )
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    if parsed.username:
        netloc = f"{quote(unquote(parsed.username), safe='')}@{netloc}"
    query = urlencode(
        (key, value)
        for key, value in query_items
        if key.casefold() != "password"
    )
    safe_url = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, query, ""))
    output = target.with_suffix(".dump")
    command = [
        "pg_dump",
        "--format=custom",
        "--file", str(output),
        safe_url,
    ]
    env = dict(os.environ)
    if password:
        env["PGPASSWORD"] = password
    subprocess.run(command, check=True, env=env)


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

    from app.services.backup_restore import backup_encryption_key_material

    key = backup_encryption_key_material()
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
