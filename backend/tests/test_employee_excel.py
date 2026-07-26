"""Personel Excel şablon / import smoke."""
from app.services.employee_excel import build_import_template_xlsx, map_header, parse_employees_workbook


def test_map_adi_soyadi_variants():
    assert map_header("Adı Soyadı") == "full_name"
    assert map_header("Ad Soyad") == "full_name"
    assert map_header("ADI SOYADI") == "full_name"
    assert map_header("TC") == "national_id_masked"
    assert map_header("Görevi") == "job_title"
    assert map_header("İşe Giriş Tarihi") == "start_date"
    assert map_header("Engelli/Hükümlü Durumu") == "special_status"


def test_parse_and_template_roundtrip():
    raw = build_import_template_xlsx()
    rows = parse_employees_workbook(raw)
    assert len(rows) >= 2
    assert rows[0]["full_name"] == "Ali Veli"
    assert rows[0]["job_title"] == "Kaynakçı"
