"""Encryption and validation service for RegulatoryIdentity.

Full TCKN/YKN values are never returned by public helpers.  Storage is fail-
closed unless REGULATORY_IDENTITY_ENCRYPTION_KEY is configured.  No fallback to
SECRET_KEY is allowed because authority identity material deserves independent
key rotation.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.regulatory_identity import RegulatoryIdentity

IdentityType = Literal["tckn", "ykn"]
PREFIX = "rid:v1:"


class RegulatoryIdentityError(ValueError):
    pass


def _key_material() -> str:
    return (os.getenv("REGULATORY_IDENTITY_ENCRYPTION_KEY") or "").strip()


def key_ready() -> bool:
    return len(_key_material()) >= 32


def _fernet() -> Fernet:
    raw = _key_material()
    if len(raw) < 32:
        raise RegulatoryIdentityError(
            "REGULATORY_IDENTITY_ENCRYPTION_KEY en az 32 karakter ve ayrı bir production secret olmalıdır."
        )
    digest = hashlib.sha256(("enc:" + raw).encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _lookup_key() -> bytes:
    raw = _key_material()
    if len(raw) < 32:
        raise RegulatoryIdentityError("Regulatory identity key is not configured.")
    return hashlib.sha256(("lookup:" + raw).encode("utf-8")).digest()


def _digits(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def valid_tckn(value: str) -> bool:
    d = _digits(value)
    if len(d) != 11 or d[0] == "0":
        return False
    nums = [int(x) for x in d]
    tenth = ((sum(nums[0:9:2]) * 7) - sum(nums[1:8:2])) % 10
    eleventh = sum(nums[:10]) % 10
    return nums[9] == tenth and nums[10] == eleventh


def validate_identity(identity_type: IdentityType, value: str) -> str:
    d = _digits(value)
    if identity_type == "tckn":
        if not valid_tckn(d):
            raise RegulatoryIdentityError("Geçerli 11 haneli T.C. Kimlik Numarası zorunludur.")
        return d
    if identity_type == "ykn":
        # Exact authority validation may become stricter when the current
        # Ministry data dictionary is supplied.  Until then only structural
        # validation is allowed; no undocumented checksum is invented.
        if len(d) not in {10, 11}:
            raise RegulatoryIdentityError("Yabancı kimlik numarası yapısal olarak geçersizdir.")
        return d
    raise RegulatoryIdentityError(f"Desteklenmeyen kimlik türü: {identity_type}")


def mask_identity(value: str) -> str:
    d = _digits(value)
    if len(d) < 4:
        return "****"
    return "*" * max(0, len(d) - 4) + d[-4:]


def lookup_hash(identity_type: IdentityType, value: str) -> str:
    normalized = validate_identity(identity_type, value)
    msg = f"{identity_type}:{normalized}".encode("utf-8")
    return hmac.new(_lookup_key(), msg, hashlib.sha256).hexdigest()


def encrypt_identity(identity_type: IdentityType, value: str) -> str:
    normalized = validate_identity(identity_type, value)
    token = _fernet().encrypt(normalized.encode("ascii")).decode("ascii")
    return PREFIX + token


def decrypt_identity(ciphertext: str) -> str:
    if not str(ciphertext or "").startswith(PREFIX):
        raise RegulatoryIdentityError("Unsupported regulatory identity ciphertext version.")
    try:
        return _fernet().decrypt(ciphertext[len(PREFIX):].encode("ascii")).decode("ascii")
    except InvalidToken as exc:
        raise RegulatoryIdentityError("Regulatory identity decrypt failed.") from exc


def upsert_employee_identity(
    db: Session,
    *,
    company_id: int,
    employee_id: int,
    identity_type: IdentityType,
    raw_value: str,
    verified_by_id: int | None = None,
    commit: bool = False,
) -> RegulatoryIdentity:
    normalized = validate_identity(identity_type, raw_value)
    row = db.scalar(
        select(RegulatoryIdentity).where(
            RegulatoryIdentity.employee_id == employee_id,
            RegulatoryIdentity.identity_type == identity_type,
        )
    )
    if row is None:
        row = RegulatoryIdentity(
            company_id=company_id,
            employee_id=employee_id,
            identity_type=identity_type,
            masked_value=mask_identity(normalized),
            ciphertext=encrypt_identity(identity_type, normalized),
            lookup_hash=lookup_hash(identity_type, normalized),
            encryption_version="rid:v1",
        )
        db.add(row)
    else:
        if row.company_id != company_id:
            raise RegulatoryIdentityError("Employee/company scope mismatch in regulatory identity vault.")
        row.masked_value = mask_identity(normalized)
        row.ciphertext = encrypt_identity(identity_type, normalized)
        row.lookup_hash = lookup_hash(identity_type, normalized)
        row.encryption_version = "rid:v1"
    if verified_by_id:
        row.verified_by_id = verified_by_id
        row.verified_at = datetime.utcnow()
    db.flush()
    if commit:
        db.commit()
        db.refresh(row)
    return row


def identity_for_authority(
    db: Session,
    *,
    company_id: int,
    employee_id: int,
    identity_type: IdentityType = "tckn",
) -> str:
    """Internal adapter-only resolver. Never expose this value in API/log/audit."""
    row = db.scalar(
        select(RegulatoryIdentity).where(
            RegulatoryIdentity.company_id == company_id,
            RegulatoryIdentity.employee_id == employee_id,
            RegulatoryIdentity.identity_type == identity_type,
        )
    )
    if row is None:
        raise RegulatoryIdentityError("Çalışanın resmî entegrasyon kimlik kaydı bulunamadı.")
    return decrypt_identity(row.ciphertext)


def public_identity_status(db: Session, *, company_id: int, employee_id: int) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(RegulatoryIdentity).where(
                RegulatoryIdentity.company_id == company_id,
                RegulatoryIdentity.employee_id == employee_id,
            )
        ).all()
    )
    return {
        "employee_id": employee_id,
        "company_id": company_id,
        "identities": [
            {
                "identity_type": row.identity_type,
                "masked_value": row.masked_value,
                "verified": bool(row.verified_at),
                "encryption_version": row.encryption_version,
            }
            for row in rows
        ],
        "full_identity_exposed": False,
    }
