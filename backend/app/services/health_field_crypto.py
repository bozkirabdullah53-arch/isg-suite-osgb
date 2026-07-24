"""Sağlık alanı şifreleme (P0-10) — envelope-benzeri Fernet, varsayılan kapalı.

Flag kapalıyken yazma düz metin (mevcut davranış).
Okuma: `enc:v1:` önekli değerler her zaman çözülür (geriye uyum).
KMS yok; anahtar HEALTH_FIELD_ENCRYPTION_KEY veya SECRET_KEY türevi.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any

from app.core.config import settings

PREFIX = "enc:v1:"

# At-rest şifrelenebilecek metin alanları (sayısal tetkik değerleri hariç — filtre/rapor)
SENSITIVE_TEXT_FIELDS: tuple[str, ...] = (
    "confidential_note",
    "summary",
    "audiometry_result",
    "spirometry_result",
    "chest_xray_result",
    "follow_up_note",
    "other_biological_test",
    "exposures",
    "suggested_tests",
)


def _fernet():
    from cryptography.fernet import Fernet

    raw = (settings.health_field_encryption_key or settings.secret_key or "").strip()
    if not raw:
        raise RuntimeError("Sağlık alanı şifreleme anahtarı yok.")
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def is_encrypted(value: str | None) -> bool:
    return bool(value) and str(value).startswith(PREFIX)


def encrypt_field(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    if is_encrypted(value):
        return value
    if not settings.health_field_encryption_enabled:
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{PREFIX}{token}"


def decrypt_field(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    if not is_encrypted(value):
        return value
    token = value[len(PREFIX) :]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:
        # Yanlış anahtar / bozuk — UI'yi tamamen kırmamak için işaretle
        return "[şifre-çözülemedi]"


def encrypt_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Create/update dict içindeki hassas alanları şifreler (flag açıksa)."""
    if not settings.health_field_encryption_enabled:
        return data
    out = dict(data)
    for key in SENSITIVE_TEXT_FIELDS:
        if key in out and out[key] is not None:
            out[key] = encrypt_field(out[key] if isinstance(out[key], str) else str(out[key]))
    return out


def decrypted_overlay(record: Any) -> dict[str, str | None]:
    return {f: decrypt_field(getattr(record, f, None)) for f in SENSITIVE_TEXT_FIELDS}


class DecryptedRecordView:
    """ORM kaydını şifresiz alanlarla okumak için proxy (commit etmez)."""

    def __init__(self, record: Any):
        self._record = record
        self._plain = decrypted_overlay(record)

    def __getattr__(self, name: str):
        if name in self._plain:
            return self._plain[name]
        return getattr(self._record, name)
