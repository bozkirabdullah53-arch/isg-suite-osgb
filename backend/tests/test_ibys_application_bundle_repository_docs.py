from __future__ import annotations

import io
import zipfile

from app.services.ibys_application_bundle import build_application_bundle


def test_repository_application_documents_build_without_unresolved_letter_placeholders():
    profile = {
        "legal_name": "Test Yazılım Anonim Şirketi",
        "tax_office": "Çankaya",
        "tax_number": "1234567890",
        "mersis_number": "0123456789012345",
        "registered_address": "Ankara Test Adresi",
        "phone": "+90 312 000 00 00",
        "corporate_email": "test@example.com",
        "website": "https://example.com",
        "representative_name": "Test Yetkilisi",
        "representative_title": "Genel Müdür",
        "signature_method": "Güvenli e-imza",
    }

    data, evidence = build_application_bundle(profile, require_attachments=False)

    assert evidence["official_registration_claim"] is False
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        letter = archive.read("01-BASVURU_DILEKCESI.md").decode("utf-8")
        appointment = archive.read("02-RANDEVU_TALEP_METNI.md").decode("utf-8")
        assert "Test Yazılım Anonim Şirketi" in letter
        assert "Test Yetkilisi" in letter
        assert "Test Yazılım Anonim Şirketi" in appointment
        assert "[ŞİRKETİN TAM TİCARİ UNVANI]" not in letter
        assert "[AD SOYAD]" not in appointment
