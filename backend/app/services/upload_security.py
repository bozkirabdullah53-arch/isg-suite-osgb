"""Upload içerik doğrulama ve karantina (basit AV-benzeri magic-byte kontrolü)."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import settings

# Uzantı → beklenen magic imzalar (en az biri eşleşmeli)
MAGIC_BY_EXT: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".xlsx": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    ".docx": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
}

# Tehlikeli / yürütülebilir imzalar — her zaman reddet
DENY_MAGIC = (
    b"MZ",  # PE/EXE
    b"\x7fELF",  # ELF
    b"#!",  # script
)


def quarantine_dir() -> Path:
    root = Path(settings.upload_dir).resolve() / "_quarantine"
    root.mkdir(parents=True, exist_ok=True)
    return root


def quarantine_bytes(content: bytes, reason: str, original_name: str = "unknown") -> str:
    """Reddedilen içeriği karantinaya yazar; dosya adı döner."""
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (original_name or "file"))[:80]
    name = f"{uuid4().hex}_{safe}.bin"
    path = quarantine_dir() / name
    meta = f"reason={reason}\noriginal={original_name}\nsize={len(content)}\n".encode()
    path.write_bytes(meta + b"\n---\n" + content[: min(len(content), 2_000_000)])
    return name


def assert_safe_upload(content: bytes, extension: str, original_name: str = "") -> None:
    """Magic-byte allowlist; başarısızsa karantinaya alıp 400."""
    ext = (extension or "").lower()
    head = content[:16] if content else b""

    for bad in DENY_MAGIC:
        if head.startswith(bad):
            quarantine_bytes(content, f"deny_magic:{bad!r}", original_name)
            raise HTTPException(status_code=400, detail="Dosya içeriği güvenlik kontrolünden geçmedi.")

    expected = MAGIC_BY_EXT.get(ext)
    if not expected:
        quarantine_bytes(content, f"unknown_ext:{ext}", original_name)
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya türü.")

    if not any(content.startswith(sig) for sig in expected):
        quarantine_bytes(content, f"magic_mismatch:{ext}", original_name)
        raise HTTPException(
            status_code=400,
            detail="Dosya uzantısı ile içerik uyuşmuyor (içerik doğrulama).",
        )
