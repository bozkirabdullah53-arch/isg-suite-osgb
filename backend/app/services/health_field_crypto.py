"""Sağlık alanı şifreleme (P0-10) — envelope-benzeri Fernet, varsayılan kapalı.

Flag kapalıyken yazma düz metin (mevcut davranış).
Okuma: `enc:v1:` önekli değerler her zaman çözülür (geriye uyum).
KMS yok; anahtar HEALTH_FIELD_ENCRYPTION_KEY veya SECRET_KEY türevi.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from typing import Any

from app.core.config import _INSECURE_SECRET_KEYS, settings

logger = logging.getLogger(__name__)
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


def encryption_key_material() -> str:
    return (settings.health_field_encryption_key or settings.secret_key or "").strip()


def _fernet_from(raw: str):
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _fernet():
    raw = encryption_key_material()
    if not raw:
        raise RuntimeError("Sağlık alanı şifreleme anahtarı yok.")
    return _fernet_from(raw)


def encryption_key_status() -> str:
    """dedicated | secret_key_fallback | weak_fallback | missing | invalid"""
    dedicated = (settings.health_field_encryption_key or "").strip()
    secret = (settings.secret_key or "").strip()
    if dedicated:
        try:
            f = _fernet_from(dedicated)
            token = f.encrypt(b"probe")
            assert f.decrypt(token) == b"probe"
            return "dedicated"
        except Exception:
            return "invalid"
    if not secret:
        return "missing"
    weak = (
        len(secret) < 32
        or secret.lower() in _INSECURE_SECRET_KEYS
        or secret.startswith("change-me")
    )
    try:
        f = _fernet_from(secret)
        token = f.encrypt(b"probe")
        assert f.decrypt(token) == b"probe"
    except Exception:
        return "invalid"
    return "weak_fallback" if weak else "secret_key_fallback"


def encryption_readiness() -> dict[str, Any]:
    """Flag kapalıyken de anahtar/probe durumunu raporlar (yazmayı değiştirmez)."""
    status = encryption_key_status()
    probe_ok = status in ("dedicated", "secret_key_fallback", "weak_fallback")
    return {
        "enabled": bool(settings.health_field_encryption_enabled),
        "key_status": status,
        "can_enable": status == "dedicated",
        "probe_ok": probe_ok,
    }


def health_crypto_ready_label() -> str:
    ready = encryption_readiness()
    if ready["probe_ok"] and ready["key_status"] != "weak_fallback":
        return "ok"
    return "not_ready"


def enable_health_crypto_for_production() -> str:
    """Production cutover: secret_key_fallback veya dedicated ile yeni yazıları şifrele."""
    env = (settings.environment or "").strip().lower()
    if env not in ("production", "prod", "live"):
        return "skipped-non-prod"
    if bool(getattr(settings, "health_field_encryption_force_off", False)):
        return "force-off"
    status = encryption_key_status()
    if status in ("dedicated", "secret_key_fallback"):
        settings.health_field_encryption_enabled = True
        logger.info("health field encryption enabled (%s)", status)
        return f"enabled:{status}"
    logger.warning("health field encryption not ready (%s)", status)
    return f"not-ready:{status}"


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
        logger.warning("health field decrypt failed", exc_info=True)
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
