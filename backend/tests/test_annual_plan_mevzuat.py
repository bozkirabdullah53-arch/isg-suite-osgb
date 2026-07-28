"""Yıllık plan şablonu + mevzuat dayanağı + PDF duman testleri."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.annual_plan_pdf import build_annual_plan_pdf
from app.services.annual_plan_template import (
    BASE_TEMPLATE,
    template_for_hazard,
)
from app.services.mevzuat_panel import build_mevzuat_panel


def test_base_template_has_legal_basis():
    assert len(BASE_TEMPLATE) >= 13
    for row in BASE_TEMPLATE:
        assert len(row) == 7
        assert row[6], "mevzuat dayanağı boş olamaz"


def test_cok_tehlikeli_has_extra_items():
    az = template_for_hazard("Az Tehlikeli")
    cok = template_for_hazard("Çok Tehlikeli")
    assert len(cok) > len(az)
    acts = {r[2] for r in cok}
    assert "Ortam ölçümleri ve maruziyet takibi planı" in acts
    assert all(r[6] for r in cok)


def test_insaat_tehlikeli_extra_not_in_az():
    az_acts = {r[2] for r in template_for_hazard("Az Tehlikeli")}
    teh_acts = {r[2] for r in template_for_hazard("Tehlikeli")}
    assert "Tehlike sınıfına göre eğitim sürelerinin gözden geçirilmesi" in teh_acts
    assert "Tehlike sınıfına göre eğitim sürelerinin gözden geçirilmesi" not in az_acts


def test_plan_pdf_contains_legal_and_title():
    items = [
        SimpleNamespace(
            id=1,
            month=1,
            category="yillik_calisma",
            activity="Yıllık İSG çalışma planının oluşturulması",
            legal_basis="İSG Hizmetleri Yönetmeliği — yıllık çalışma planı",
            responsible_name="Uzman Test",
            target_date=date(2026, 1, 15),
            status=SimpleNamespace(value="planned"),
        )
    ]
    pdf = build_annual_plan_pdf(
        company_name="Test A.Ş.",
        year=2026,
        items=items,
        hazard_class="Çok Tehlikeli",
        specialist_name="Uzman",
        physician_name="Hekim",
        employer_name="İşveren",
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 800


def test_mevzuat_panel_has_yillik_plan_highlight():
    panel = build_mevzuat_panel()
    ids = {h["id"] for h in panel.get("highlights") or []}
    assert "yillik-plan" in ids
