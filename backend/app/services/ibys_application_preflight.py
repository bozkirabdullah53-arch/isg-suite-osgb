"""İBYS başvuru hazırlığını hassas veri döndürmeden puanlayan ön kontrol motoru."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.ibys_application_bundle import (
    PLACEHOLDER_RE,
    REQUIRED_ATTACHMENT_GROUPS,
    REQUIRED_PROFILE_FIELDS,
)

PREFLIGHT_VERSION = "ibys-application-preflight-v1"
TECHNICAL_BASE_PERCENT = 80

DOCUMENT_TITLES = {
    "trade_registry": "Ticaret sicili / Ticaret Sicil Gazetesi",
    "activity_certificate": "Güncel faaliyet belgesi",
    "tax_certificate": "Vergi levhası",
    "signature_circular": "İmza sirküleri / yetki belgesi",
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _profile_gaps(profile: dict[str, Any]) -> tuple[list[str], list[str]]:
    cleaned = {str(key): _clean_text(value) for key, value in profile.items()}
    missing = [field for field in REQUIRED_PROFILE_FIELDS if not cleaned.get(field)]
    placeholders = sorted(
        field
        for field, value in cleaned.items()
        if value and (PLACEHOLDER_RE.search(value) or value.upper() in {"TBD", "TODO"} or value in {"...", "-"})
    )
    return sorted(missing), placeholders


def _attachment_report(filenames: list[str]) -> tuple[dict[str, str], list[str]]:
    safe_names = [Path(_clean_text(name)).name for name in filenames if _clean_text(name)]
    matched: dict[str, str] = {}
    missing: list[str] = []
    for group, tokens in REQUIRED_ATTACHMENT_GROUPS.items():
        found = next(
            (
                name
                for name in safe_names
                if all(token.casefold() in name.casefold() for token in tokens)
            ),
            None,
        )
        if found:
            matched[group] = found
        else:
            missing.append(group)
    return matched, missing


def assess_application_preflight(
    company_profile: dict[str, Any],
    *,
    attachment_filenames: list[str] | None = None,
    legal_kvkk_approved: bool = False,
    external_authorization_smoke_completed: bool = False,
    application_letter_signed: bool = False,
    appointment_package_approved: bool = False,
) -> dict[str, Any]:
    """Başvuru hazırlığını kanıt kapılarıyla puanlar; profil değerlerini yanıta koymaz."""
    attachment_filenames = attachment_filenames or []
    missing_profile_fields, placeholder_profile_fields = _profile_gaps(company_profile)
    profile_complete = not missing_profile_fields and not placeholder_profile_fields

    matched_documents, missing_document_codes = _attachment_report(attachment_filenames)
    all_documents_present = not missing_document_codes

    profile_points = 5 if profile_complete else 0
    document_points = len(matched_documents) * 2
    if all_documents_present:
        document_points += 2
    legal_points = 2 if legal_kvkk_approved else 0
    smoke_points = 1 if external_authorization_smoke_completed else 0
    signature_points = 1 if application_letter_signed else 0
    appointment_points = 1 if appointment_package_approved else 0

    score = min(
        100,
        TECHNICAL_BASE_PERCENT
        + profile_points
        + document_points
        + legal_points
        + smoke_points
        + signature_points
        + appointment_points,
    )
    ready_for_bundle = profile_complete and all_documents_present
    ready_for_submission = ready_for_bundle and all(
        (
            legal_kvkk_approved,
            external_authorization_smoke_completed,
            application_letter_signed,
            appointment_package_approved,
        )
    )

    return {
        "preflight_version": PREFLIGHT_VERSION,
        "official_registration_claim": False,
        "application_preparation_percent": score,
        "technical_base_percent": TECHNICAL_BASE_PERCENT,
        "ready_for_bundle": ready_for_bundle,
        "ready_for_submission": ready_for_submission,
        "profile": {
            "complete": profile_complete,
            "points": profile_points,
            "max_points": 5,
            "missing_fields": missing_profile_fields,
            "placeholder_fields": placeholder_profile_fields,
        },
        "corporate_documents": {
            "complete": all_documents_present,
            "points": document_points,
            "max_points": 10,
            "matched": [
                {"code": code, "title": DOCUMENT_TITLES[code], "filename": filename}
                for code, filename in sorted(matched_documents.items())
            ],
            "missing": [
                {"code": code, "title": DOCUMENT_TITLES[code]}
                for code in missing_document_codes
            ],
        },
        "evidence_gates": {
            "legal_kvkk_approved": legal_kvkk_approved,
            "external_authorization_smoke_completed": external_authorization_smoke_completed,
            "application_letter_signed": application_letter_signed,
            "appointment_package_approved": appointment_package_approved,
        },
        "remaining_actions": [
            action
            for condition, action in (
                (not profile_complete, "Şirket profilindeki eksik veya şablon alanları tamamlayın."),
                (not all_documents_present, "Zorunlu kurumsal belgeleri yükleyin ve doğrulayın."),
                (not legal_kvkk_approved, "Hukuk/KVKK yetkilisi onayını kanıtıyla tamamlayın."),
                (
                    not external_authorization_smoke_completed,
                    "Yetkisiz erişim ve rol kapsamı dış smoke test kanıtını tamamlayın.",
                ),
                (not application_letter_signed, "Başvuru dilekçesini yetkili kişiye imzalatın."),
                (not appointment_package_approved, "İSGGM randevu paketinin nihai onayını tamamlayın."),
            )
            if condition
        ],
        "note": (
            "Bu oran başvuru dosyası hazırlığıdır; Bakanlık tescili veya resmî İBYS teknik uygunluğu değildir. "
            "Boolean kanıt kapıları yetkili kullanıcı beyanıdır ve belge/audit kanıtıyla doğrulanmalıdır."
        ),
    }
