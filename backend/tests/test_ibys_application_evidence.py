from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.ibys_application_evidence import (
    EVIDENCE_LEDGER_VERSION,
    assess_verified_application_preflight,
    validate_evidence_ledger,
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


def _evidence_item(seed: str) -> dict[str, str | bool]:
    return {
        "completed": True,
        "verified_by": "Yetkili Kontrolör",
        "verified_at": "2026-08-05T09:00:00+03:00",
        "evidence_reference": f"KANIT-{seed}",
        "sha256": (seed.lower()[0] if seed else "a") * 64,
    }


def _ledger() -> dict:
    documents = [
        ("trade_registry", "ticaret-sicil-gazetesi.pdf", "a"),
        ("activity_certificate", "faaliyet-belgesi.pdf", "b"),
        ("tax_certificate", "vergi-levhasi.pdf", "c"),
        ("signature_circular", "imza-sirkuleri.pdf", "d"),
    ]
    return {
        "application_reference": "IBYS-BASVURU-2026-001",
        "corporate_documents": [
            {
                "code": code,
                "filename": filename,
                **_evidence_item(seed),
            }
            for code, filename, seed in documents
        ],
        "gates": {
            "legal_kvkk_approval": _evidence_item("e"),
            "external_authorization_smoke": _evidence_item("f"),
            "application_letter_signature": _evidence_item("1"),
            "appointment_package_approval": _evidence_item("2"),
        },
    }


def test_complete_evidence_ledger_is_valid_and_drives_verified_100_percent():
    validation = validate_evidence_ledger(_ledger())
    result = assess_verified_application_preflight(_profile(), _ledger())

    assert validation["ledger_version"] == EVIDENCE_LEDGER_VERSION
    assert validation["valid"] is True
    assert validation["errors"] == []
    assert len(validation["verified_documents"]) == 4
    assert len(validation["verified_gates"]) == 4
    assert result["strict_evidence_mode"] is True
    assert result["application_preparation_percent"] == 100
    assert result["ready_for_submission"] is True
    assert _profile()["tax_number"] not in str(result)


def test_sensitive_identifier_keys_are_forbidden_in_evidence_ledger():
    ledger = _ledger()
    ledger["tax_number"] = "1234567890"

    validation = validate_evidence_ledger(ledger)
    result = assess_verified_application_preflight(_profile(), ledger)

    assert validation["valid"] is False
    assert "tax_number" in validation["sensitive_paths"]
    assert any("sensitive key forbidden" in error for error in validation["errors"])
    assert result["application_preparation_percent"] == 100
    assert result["ready_for_submission"] is False


def test_invalid_gate_hash_does_not_award_gate_point():
    ledger = _ledger()
    ledger["gates"]["external_authorization_smoke"]["sha256"] = "invalid"

    validation = validate_evidence_ledger(ledger)
    result = assess_verified_application_preflight(_profile(), ledger)

    assert validation["valid"] is False
    assert "external_authorization_smoke" in validation["missing_gates"]
    assert validation["gate_flags"]["external_authorization_smoke_completed"] is False
    assert result["application_preparation_percent"] == 99
    assert result["ready_for_submission"] is False


def test_duplicate_or_mismatched_document_is_rejected():
    ledger = _ledger()
    ledger["corporate_documents"][1]["code"] = "trade_registry"
    ledger["corporate_documents"][2]["filename"] = "rastgele.pdf"

    validation = validate_evidence_ledger(ledger)

    assert validation["valid"] is False
    assert any("duplicate document code" in error for error in validation["errors"])
    assert any("filename does not match document code" in error for error in validation["errors"])
    assert "activity_certificate" in validation["missing_documents"]
    assert "tax_certificate" in validation["missing_documents"]


def test_evidence_routes_registered_and_anonymous_requests_denied():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/ibys-application/evidence/validate" in paths
    assert "/api/v1/ibys-application/preflight/verified" in paths

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ibys-application/preflight/verified",
            json={"company_profile": _profile(), "evidence_ledger": _ledger()},
        )

    assert response.status_code in {401, 403}
    assert "application_preparation_percent" not in response.text
    assert _profile()["tax_number"] not in response.text
