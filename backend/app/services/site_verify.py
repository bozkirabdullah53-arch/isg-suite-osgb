"""İşyeri saha QR doğrulama kodu."""
from __future__ import annotations

import re
import secrets

QR_PREFIX = "ISGSUITE:WP:"


def generate_site_verify_code() -> str:
    return secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12].upper()


def build_qr_payload(company_id: int, code: str) -> str:
    return f"{QR_PREFIX}{company_id}:{code}"


def parse_site_code(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if text.upper().startswith(QR_PREFIX):
        tail = text[len(QR_PREFIX) :]
        parts = tail.split(":", 1)
        if len(parts) == 2:
            return parts[1].strip().upper()
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def codes_match(company_code: str | None, raw: str | None) -> bool:
    if not company_code:
        return True
    submitted = parse_site_code(raw or "")
    return bool(submitted) and submitted == company_code.strip().upper()
