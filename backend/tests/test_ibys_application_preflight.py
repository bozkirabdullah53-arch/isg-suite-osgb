from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.ibys_application_preflight import (
    PREFLIGHT_VERSION,
    assess_application_preflight,
)


def _profile() -> dict[str, str]:
    return {
        "legal_name": "Örnek Yazılım Anonim Şirketi",
        "tax_office": "Çankaya",
        "tax_number": "1234567890",
        "mersis_number": "0123456789012345",
        "registered_address": "Emek Mahallesi, Ankara",
        "phone": "+90 312 000 00 00",
        "corporate_email": "ibys@example.com",
        "website": "https://example.com",
        "representative_name": "Örnek Yetkili",
        "representative_title": "Genel Müdür",
        "signature_method": "Güvenli e-imza",
    }


def _attachments() -> list[str]:
    return [
        "ticaret-sicil-gazetesi.pdf",
        "faaliyet-belgesi.pdf",
        "vergi-levhasi.pdf",
        "imza-sirkuleri.pdf",
    ]


def test_preflight_starts_from_verified_technical_base_without_claiming_registration():
    result = assess_application_preflight({})

    assert result["preflight_version"] == PREFLIGHT_VERSION
    assert result["application_preparation_percent"] == 80
    assert result["technical_base_percent"] == 80
    assert result["official_registration_claim"] is False
    assert result["ready_for_bundle"] is False
    assert result["ready_for_submission"] is False
    assert set(result["profile"]["missing_fields"]) >= {
        "legal_name",
        "tax_number",
        "mersis_number",
        "representative_name",
    }
    assert len(result["corporate_documents"]["missing"]) == 4


def test_complete_profile_and_required_documents_reach_bundle_ready_95_percent():
    secret_tax_number = _profile()["tax_number"]

    result = assess_application_preflight(
        _profile(),
        attachment_filenames=[f"../../{name}" for name in _attachments()],
    )

    assert result["application_preparation_percent"] == 95
    assert result["profile"]["complete"] is True
    assert result["corporate_documents"]["complete"] is True
    assert result["ready_for_bundle"] is True
    assert result["ready_for_submission"] is False
    assert secret_tax_number not in str(result)
    assert all("/" not in item["filename"] for item in result["corporate_documents"]["matched"])


def test_all_evidence_gates_reach_100_and_submission_ready():
    result = assess_application_preflight(
        _profile(),
        attachment_filenames=_attachments(),
        legal_kvkk_approved=True,
        external_authorization_smoke_completed=True,
        application_letter_signed=True,
        appointment_package_approved=True,
    )

    assert result["application_preparation_percent"] == 100
    assert result["ready_for_bundle"] is True
    assert result["ready_for_submission"] is True
    assert result["remaining_actions"] == []


def test_placeholder_profile_value_blocks_bundle_even_with_all_documents():
    profile = _profile()
    profile["representative_title"] = "[UNVAN]"

    result = assess_application_preflight(profile, attachment_filenames=_attachments())

    assert result["application_preparation_percent"] == 90
    assert result["profile"]["complete"] is False
    assert result["profile"]["placeholder_fields"] == ["representative_title"]
    assert result["ready_for_bundle"] is False


def test_preflight_route_is_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/ibys-application/preflight" in paths


def test_preflight_route_rejects_anonymous_request_without_leaking_report():
    from app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ibys-application/preflight",
            json={"company_profile": _profile(), "attachment_filenames": _attachments()},
        )

    assert response.status_code in {401, 403}
    body = response.text
    assert "application_preparation_percent" not in body
    assert _profile()["tax_number"] not in body
