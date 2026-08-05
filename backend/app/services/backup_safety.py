"""Integrity and resource-safety checks for tenant backup archives."""
from __future__ import annotations

import hashlib
import hmac
import zipfile
from pathlib import Path, PurePosixPath

from fastapi import HTTPException

MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive_checksum(path: Path, expected_checksum: str | None) -> str:
    """Return verified/not-recorded; raise when a recorded checksum mismatches."""
    expected = (expected_checksum or "").strip().lower()
    if not expected:
        return "not-recorded"
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise HTTPException(status_code=409, detail="Arşiv checksum kaydı geçersiz.")
    actual = sha256_file(path)
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(
            status_code=409,
            detail="Arşiv bütünlük doğrulaması başarısız; dosya değiştirilmiş veya bozulmuş.",
        )
    return "verified"


def validate_zip_safety(zf: zipfile.ZipFile) -> dict[str, int]:
    """Reject ambiguous paths and archives that could exhaust restore resources."""
    members = zf.infolist()
    if len(members) > MAX_ZIP_ENTRIES:
        raise HTTPException(status_code=413, detail="Yedek çok fazla dosya içeriyor.")

    seen: set[str] = set()
    total = 0
    file_count = 0
    for info in members:
        normalized = str(PurePosixPath(info.filename))
        if normalized in seen:
            raise HTTPException(status_code=400, detail="Yedekte yinelenen dosya yolu var.")
        seen.add(normalized)

        parts = PurePosixPath(info.filename).parts
        if info.filename.startswith(("/", "\\")) or ".." in parts:
            raise HTTPException(status_code=400, detail="Yedekte güvenli olmayan dosya yolu var.")
        if info.is_dir():
            continue

        file_count += 1
        if info.file_size > MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES:
            raise HTTPException(status_code=413, detail="Yedekte izin verilen boyutu aşan dosya var.")
        total += info.file_size
        if total > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
            raise HTTPException(status_code=413, detail="Yedeğin açılmış toplam boyutu güvenli sınırı aşıyor.")

    return {
        "entry_count": len(members),
        "file_count": file_count,
        "uncompressed_bytes": total,
    }


def validate_backup_archive(path: Path) -> dict[str, int]:
    """Decrypt when needed and run ZIP safety checks without restoring anything."""
    from app.services.backup_restore import _decrypt_if_needed

    work = _decrypt_if_needed(path)
    cleanup = work != path
    try:
        if not zipfile.is_zipfile(work):
            raise HTTPException(status_code=400, detail="Yedek ZIP değil veya bozuk.")
        with zipfile.ZipFile(work, "r") as zf:
            return validate_zip_safety(zf)
    finally:
        if cleanup:
            try:
                work.unlink(missing_ok=True)
            except OSError:
                pass
