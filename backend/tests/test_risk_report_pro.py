"""Risk rapor yöntemleri + profesyonel PDF duman testleri."""
from datetime import date
from types import SimpleNamespace

from app.services.risk_methods import method_choices, resolve_method
from app.services.risk_reports import build_risk_pdf
from app.services.risk_validity import build_validity, document_meta_rows


def test_methods_catalog_covers_common_methods():
    codes = {m["code"] for m in method_choices()}
    for needed in ("5x5_l", "fine_kinney", "hazop", "fmea", "jsa", "what_if", "x_matrix"):
        assert needed in codes
    assert "Fine-Kinney" in resolve_method("fine_kinney")["label"]


def test_validity_uses_selected_method():
    v = build_validity(
        hazard_class="Çok Tehlikeli",
        assessment_date=date(2024, 7, 28),
        method_code="fine_kinney",
    )
    assert "Fine-Kinney" in v["method"]
    assert v["method_code"] == "fine_kinney"


def test_document_meta_includes_doc_control():
    rows = dict(
        document_meta_rows(
            validity={"method": "5x5", "assessment_date": "2024-07-28", "valid_until": "2026-07-28"},
            prepared_by="Uzman",
            document_no="RD-001",
            revision_no="01",
            revision_reason="Yeni makine",
        )
    )
    assert rows["Belge No"] == "RD-001"
    assert rows["Revizyon No"] == "01"
    assert rows["Revizyon Nedeni"] == "Yeni makine"


def test_professional_pdf_has_sections():
    company = SimpleNamespace(
        id=1,
        name="TEST İŞYERİ",
        authorized_person="TEST İK",
        phone="555",
        address="Adres",
        hazard_class="Çok Tehlikeli",
        sgk_registry_no="123",
        tax_number=None,
        nace_code=None,
        risk_method="5x5_l",
        risk_document_no="RD-TEST",
        risk_revision_no="00",
        risk_revision_reason=None,
        risk_scope_note=None,
    )
    risk = SimpleNamespace(
        risk_code="RSK-0001",
        department_name="Depo",
        activity="Elle taşıma",
        hazard_id=1,
        risk_definition="Gürültü / düşme riski",
        affected_people="Çalışanlar",
        affected_group=None,
        probability=4,
        severity=4,
        risk_score=16,
        risk_level="Yüksek",
        term_date=date(2026, 8, 1),
        status="Açık",
        existing_measures="yok",
        additional_measures="KKD",
        revision_no=1,
        dofs=[],
    )
    hazard = SimpleNamespace(id=1, code="FZK-001", name="Gürültü", regulations='["6331"]')
    pdf = build_risk_pdf(
        company=company,
        risks=[risk],
        hazard_map={1: hazard},
        prepared_by="Uzman Test",
        sgk_no="123",
        workplace_physician="Hekim",
        employer_representative="TEST İK",
        employee_representative="Temsilci",
        support_staff="Destek",
        validity=build_validity(
            hazard_class="Çok Tehlikeli",
            assessment_date=date(2024, 7, 28),
            method_code="5x5_l",
        ),
        employee_count=12,
        document_no="RD-TEST",
        revision_no="00",
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2500
