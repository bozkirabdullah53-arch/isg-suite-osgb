"""İBYS başvuru kanıt defterini hassas veri içermeden doğrular."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.ibys_application_bundle import REQUIRED_ATTACHMENT_GROUPS
from app.services.ibys_application_preflight import assess_application_preflight

EVIDENCE_LEDGER_VERSION = "ibys-application-evidence-ledger-v1"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
PLACEHOLDER_VALUES = {"", "-", "...", "tbd", "todo", "pending", "bekliyor"}
SENSITIVE_KEY_FRAGMENTS = (
    "tax_number",
    "mersis_number",
    "national_id",
    "tckn",
    "password",
    "secret",
    "api_key",
    "token",
)
REQUIRED_GATE_CODES = (
    "legal_kvkk_approval",
    "external_authorization_smoke",
    "application_letter_signature",
    "appointment_package_approval",
)
GATE_FLAG_MAP = {
    "legal_kvkk_approval": "legal_kvkk_approved",
    "external_authorization_smoke": "external_authorization_smoke_completed",
    "application_letter_signature": "application_letter_signed",
    "appointment_package_approval": "appointment_package_approved",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_placeholder(value: Any) -> bool:
    text = _text(value)
    return text.casefold() in PLACEHOLDER_VALUES or ("[" in text and "]" in text)


def _valid_timestamp(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _find_sensitive_paths(value: Any, *, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            lowered = key_text.casefold()
            if any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS):
                found.append(path)
            found.extend(_find_sensitive_paths(child, prefix=path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_sensitive_paths(child, prefix=f"{prefix}[{index}]"))
    return found


def _validate_common_evidence(item: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    for field in ("verified_by", "verified_at", "evidence_reference", "sha256"):
        if _has_placeholder(item.get(field)):
            errors.append(f"{path}.{field}: required verified value missing")
    if not _valid_timestamp(item.get("verified_at")):
        errors.append(f"{path}.verified_at: timezone-aware ISO timestamp required")
    if not SHA256_RE.fullmatch(_text(item.get("sha256"))):
        errors.append(f"{path}.sha256: 64 character SHA-256 required")
    return errors


def validate_evidence_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    """Kanıtları ayrı ayrı doğrular; eksik kalemleri ve türetilmiş gate flag'lerini döndürür."""
    errors: list[str] = []
    sensitive_paths = _find_sensitive_paths(ledger)
    if sensitive_paths:
        errors.extend(f"sensitive key forbidden: {path}" for path in sensitive_paths)

    application_reference = _text(ledger.get("application_reference"))
    if _has_placeholder(application_reference):
        errors.append("application_reference: required non-placeholder value missing")

    verified_documents: list[dict[str, str]] = []
    seen_document_codes: set[str] = set()
    documents = ledger.get("corporate_documents")
    if not isinstance(documents, list):
        errors.append("corporate_documents: list required")
        documents = []
    for index, raw in enumerate(documents):
        path = f"corporate_documents[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{path}: object required")
            continue
        code = _text(raw.get("code"))
        if code not in REQUIRED_ATTACHMENT_GROUPS:
            errors.append(f"{path}.code: unsupported document code")
            continue
        if code in seen_document_codes:
            errors.append(f"{path}.code: duplicate document code")
            continue
        seen_document_codes.add(code)
        filename = Path(_text(raw.get("filename"))).name
        if _has_placeholder(filename):
            errors.append(f"{path}.filename: safe filename required")
        tokens = REQUIRED_ATTACHMENT_GROUPS[code]
        if filename and not all(token.casefold() in filename.casefold() for token in tokens):
            errors.append(f"{path}.filename: filename does not match document code")
        item_errors = _validate_common_evidence(raw, path=path)
        errors.extend(item_errors)
        if not item_errors and filename and all(token.casefold() in filename.casefold() for token in tokens):
            verified_documents.append(
                {
                    "code": code,
                    "filename": filename,
                    "sha256": _text(raw.get("sha256")).lower(),
                    "verified_by": _text(raw.get("verified_by")),
                    "verified_at": _text(raw.get("verified_at")),
                    "evidence_reference": _text(raw.get("evidence_reference")),
                }
            )

    verified_codes = {item["code"] for item in verified_documents}
    missing_documents = sorted(set(REQUIRED_ATTACHMENT_GROUPS) - verified_codes)

    gates = ledger.get("gates")
    if not isinstance(gates, dict):
        errors.append("gates: object required")
        gates = {}
    verified_gates: list[str] = []
    gate_flags = {flag: False for flag in GATE_FLAG_MAP.values()}
    for code in REQUIRED_GATE_CODES:
        raw = gates.get(code)
        path = f"gates.{code}"
        if not isinstance(raw, dict):
            errors.append(f"{path}: object required")
            continue
        if raw.get("completed") is not True:
            errors.append(f"{path}.completed: must be true")
            continue
        item_errors = _validate_common_evidence(raw, path=path)
        errors.extend(item_errors)
        if not item_errors:
            verified_gates.append(code)
            gate_flags[GATE_FLAG_MAP[code]] = True

    missing_gates = [code for code in REQUIRED_GATE_CODES if code not in verified_gates]
    return {
        "ledger_version": EVIDENCE_LEDGER_VERSION,
        "official_registration_claim": False,
        "valid": not errors and not missing_documents and not missing_gates,
        "application_reference_present": bool(application_reference and not _has_placeholder(application_reference)),
        "errors": errors,
        "sensitive_paths": sensitive_paths,
        "verified_documents": verified_documents,
        "missing_documents": missing_documents,
        "verified_gates": verified_gates,
        "missing_gates": missing_gates,
        "gate_flags": gate_flags,
    }


def assess_verified_application_preflight(
    company_profile: dict[str, Any],
    evidence_ledger: dict[str, Any],
) -> dict[str, Any]:
    """Ön kontrol puanını yalnız doğrulanmış kanıt defterinden türetir."""
    validation = validate_evidence_ledger(evidence_ledger)
    flags = validation["gate_flags"]
    result = assess_application_preflight(
        company_profile,
        attachment_filenames=[item["filename"] for item in validation["verified_documents"]],
        legal_kvkk_approved=flags["legal_kvkk_approved"],
        external_authorization_smoke_completed=flags["external_authorization_smoke_completed"],
        application_letter_signed=flags["application_letter_signed"],
        appointment_package_approved=flags["appointment_package_approved"],
    )
    result["strict_evidence_mode"] = True
    result["evidence_validation"] = validation
    result["ready_for_submission"] = bool(result["ready_for_submission"] and validation["valid"])
    return result
