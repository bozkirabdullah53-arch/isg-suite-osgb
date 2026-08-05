from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from app.services.ibys_application_bundle import (
    build_application_bundle,
    render_template,
    validate_company_profile,
    validate_required_attachments,
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


def _write_docs(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "BASVURU_DILEKCESI_TASLAGI.md").write_text(
        "[ŞİRKETİN TAM TİCARİ UNVANI] [VERGİ NUMARASI] [AD SOYAD]",
        encoding="utf-8",
    )
    (root / "RANDEVU_TALEP_METNI.md").write_text(
        "[TİCARİ UNVAN] [KURUMSAL E-POSTA]",
        encoding="utf-8",
    )
    (root / "TEKNIK_UYGUNLUK_MATRISI.md").write_text("teknik kanıt", encoding="utf-8")


def _write_attachments(root: Path) -> None:
    root.mkdir(parents=True)
    for name in (
        "ticaret-sicil-gazetesi.pdf",
        "faaliyet-belgesi.pdf",
        "vergi-levhasi.pdf",
        "imza-sirkuleri.pdf",
    ):
        (root / name).write_bytes(("fixture:" + name).encode("utf-8"))


def test_company_profile_fails_closed_on_missing_or_placeholder_value():
    profile = _profile()
    profile["tax_number"] = ""
    profile["representative_title"] = "[UNVAN]"

    with pytest.raises(ValueError) as exc:
        validate_company_profile(profile)

    message = str(exc.value)
    assert "missing=tax_number" in message
    assert "placeholder=representative_title" in message


def test_template_rendering_rejects_unknown_placeholder():
    with pytest.raises(ValueError, match="unresolved application placeholders"):
        render_template("[BİLİNMEYEN ALAN]", _profile())


def test_required_attachments_are_detected_by_safe_filename_tokens(tmp_path: Path):
    attachments = tmp_path / "attachments"
    _write_attachments(attachments)

    result = validate_required_attachments(attachments.iterdir())

    assert set(result) == {
        "trade_registry",
        "activity_certificate",
        "tax_certificate",
        "signature_circular",
    }


def test_bundle_fails_when_a_required_corporate_document_is_missing(tmp_path: Path):
    docs = tmp_path / "docs"
    attachments = tmp_path / "attachments"
    _write_docs(docs)
    _write_attachments(attachments)
    (attachments / "imza-sirkuleri.pdf").unlink()

    with pytest.raises(ValueError, match="signature_circular"):
        build_application_bundle(
            _profile(), docs_dir=docs, attachments_dir=attachments, require_attachments=True
        )


def test_bundle_contains_rendered_letters_attachments_and_hash_manifest(tmp_path: Path):
    docs = tmp_path / "docs"
    attachments = tmp_path / "attachments"
    _write_docs(docs)
    _write_attachments(attachments)

    data, evidence = build_application_bundle(
        _profile(), docs_dir=docs, attachments_dir=attachments, require_attachments=True
    )

    assert evidence["official_registration_claim"] is False
    assert evidence["company"]["tax_number_masked"].endswith("7890")
    assert evidence["company"]["tax_number_masked"] != _profile()["tax_number"]

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        assert "00-BUNDLE-MANIFEST.json" in names
        assert "01-BASVURU_DILEKCESI.md" in names
        assert "02-RANDEVU_TALEP_METNI.md" in names
        assert "teknik-ekler/TEKNIK_UYGUNLUK_MATRISI.md" in names
        assert "kurumsal-ekler/ticaret-sicil-gazetesi.pdf" in names

        letter = archive.read("01-BASVURU_DILEKCESI.md").decode("utf-8")
        assert "Örnek Yazılım Anonim Şirketi" in letter
        assert "[" not in letter

        manifest = json.loads(archive.read("00-BUNDLE-MANIFEST.json"))
        assert manifest["bundle_version"] == "ibys-application-bundle-v1"
        assert manifest["official_registration_claim"] is False
        assert all(len(item["sha256"]) == 64 for item in manifest["files"])
