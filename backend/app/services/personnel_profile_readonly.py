"""Dijital Personel Kartı Faz 2 — salt okunur ve veri-minimum özetler.

Bu servis mevcut Employee/IsgProfessional kayıtlarını değiştirmez. Sağlık, adli
sicil, özel durum veya başka restricted veri üretmez. Kimlik değeri hiçbir zaman
ham biçimde döndürülmez.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


READINESS_VERSION = "personnel-profile-readiness-v1"
SUMMARY_VERSION = "personnel-profile-summary-v1"


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def mask_national_identity(value: str | None) -> str | None:
    """TCKN/kimlik referansını minimum biçimde maskeler.

    Beşten az rakam varsa anlamlı parça döndürülmez. Ham değer, hata mesajı veya
    log üretilmez. Örnek: 12345678990 -> 123******90.
    """

    text = str(value or "").strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 5:
        return None
    return f"{digits[:3]}******{digits[-2:]}"


def build_employee_profile_summary(
    employee: Any,
    *,
    company_name: str | None = None,
    branch_name: str | None = None,
    rollout: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Mevcut işyeri çalışanından restricted alan içermeyen profil özeti."""

    return {
        "summary_version": SUMMARY_VERSION,
        "subject": {
            "type": "employee",
            "id": int(employee.id),
        },
        "scope": {
            "company_id": int(employee.company_id),
            "company_name": company_name,
            "branch_id": int(employee.branch_id) if employee.branch_id is not None else None,
            "branch_name": branch_name,
        },
        "profile": {
            "full_name": str(employee.full_name or "").strip(),
            "national_identity_masked": mask_national_identity(
                getattr(employee, "national_id_masked", None)
            ),
            "job_title": getattr(employee, "job_title", None),
            "department": getattr(employee, "department", None),
            "employment_start_date": _iso(getattr(employee, "start_date", None)),
            "employment_status": "active" if bool(getattr(employee, "is_active", False)) else "inactive",
        },
        "privacy": {
            "data_minimized": True,
            "national_identity_full_included": False,
            "special_status_included": False,
            "health_data_included": False,
            "criminal_record_included": False,
            "restricted_documents_included": False,
        },
        "capabilities": {
            "read_only_summary": True,
            "profile_record_management": False,
            "file_upload": False,
            "cv_generation": False,
            "external_sharing": False,
            "restricted_data": False,
        },
        "rollout": rollout or {},
    }


def build_professional_profile_summary(
    professional: Any,
    *,
    company_id: int,
    company_name: str | None = None,
    active_assignment_count: int = 0,
    rollout: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """OSGB profesyonelinden minimum, salt okunur mesleki profil özeti."""

    return {
        "summary_version": SUMMARY_VERSION,
        "subject": {
            "type": "professional",
            "id": int(professional.id),
        },
        "scope": {
            "osgb_id": int(professional.osgb_id),
            "company_id": int(company_id),
            "company_name": company_name,
        },
        "profile": {
            "full_name": str(professional.full_name or "").strip(),
            "professional_type": _enum_value(professional.professional_type),
            "email": getattr(professional, "email", None),
            "phone": getattr(professional, "phone", None),
            "certificate_class": getattr(professional, "certificate_class", None),
            "certificate_number": getattr(professional, "certificate_number", None),
            "certificate_date": _iso(getattr(professional, "certificate_date", None)),
            "employment_status": "active" if bool(getattr(professional, "is_active", False)) else "suspended",
            "active_assignment_count": max(0, int(active_assignment_count or 0)),
        },
        "privacy": {
            "data_minimized": True,
            "national_identity_full_included": False,
            "special_status_included": False,
            "health_data_included": False,
            "criminal_record_included": False,
            "restricted_documents_included": False,
        },
        "capabilities": {
            "read_only_summary": True,
            "profile_record_management": False,
            "file_upload": False,
            "cv_generation": False,
            "external_sharing": False,
            "restricted_data": False,
        },
        "rollout": rollout or {},
    }


def build_personnel_profile_readiness(
    *,
    company_id: int,
    rollout: dict[str, bool],
) -> dict[str, Any]:
    """Hassas içerik ve allowlist üyeleri açıklamayan readiness yanıtı."""

    active = bool(rollout.get("active"))
    return {
        "readiness_version": READINESS_VERSION,
        "company_id": int(company_id),
        "enabled": active,
        "visible": active,
        "read_only": True,
        "core_personnel_unaffected": True,
        "existing_employee_import_unaffected": True,
        "existing_professional_workflow_unaffected": True,
        "rollout": dict(rollout),
        "capabilities": {
            "employee_summary": True,
            "professional_summary": True,
            "profile_record_management": False,
            "file_upload": False,
            "photo_management": False,
            "cv_generation": False,
            "external_sharing": False,
            "restricted_data": False,
        },
        "legal_readiness": {
            "ordinary_professional_summary": "technical_ready_for_pilot" if active else "feature_disabled",
            "restricted_data": "legal_and_organizational_review_required",
            "external_sharing": "legal_and_organizational_review_required",
            "retention_policy": "configuration_required_before_document_storage",
        },
        "next_action": (
            "Yetkili kullanıcı salt okunur minimum profil özetini görüntüleyebilir."
            if active
            else "Personel kartı bu şirket için kapalı; mevcut personel akışı aynen devam eder."
        ),
    }
