"""Personel Excel şablon / import smoke."""
from datetime import date
from io import BytesIO

from openpyxl import Workbook, load_workbook

from app.services.employee_excel import (
    TEMPLATE_DATA_ROWS,
    TEMPLATE_DATA_START,
    TEMPLATE_HEADERS,
    TEMPLATE_SHEET_NAME,
    build_import_template_xlsx,
    map_header,
    parse_employees_workbook,
)


def test_map_adi_soyadi_variants():
    assert map_header("Adı Soyadı") == "full_name"
    assert map_header("Ad Soyad") == "full_name"
    assert map_header("ADI SOYADI") == "full_name"
    assert map_header("TC") == "national_id_masked"
    assert map_header("TC Kimlik No") == "national_id_masked"
    assert map_header("Görevi") == "job_title"
    assert map_header("İşe Giriş Tarihi") == "start_date"
    assert map_header("Giriş Tarihi") == "start_date"
    assert map_header("Çıkış Tarihi") == "exit_date"
    assert map_header("İşten Çıkış Tarihi") == "exit_date"
    assert map_header("Engelli/Hükümlü") == "special_status"
    assert map_header("Engelli/Hükümlü Durumu") == "special_status"
    assert map_header("#") == ""


def test_blank_template_does_not_import_placeholder_rows():
    rows = parse_employees_workbook(build_import_template_xlsx())
    assert rows == []


def test_template_matches_user_sample_layout():
    wb = load_workbook(BytesIO(build_import_template_xlsx()))
    assert wb.sheetnames == [TEMPLATE_SHEET_NAME]
    ws = wb[TEMPLATE_SHEET_NAME]
    assert [ws.cell(1, i).value for i in range(1, len(TEMPLATE_HEADERS) + 1)] == TEMPLATE_HEADERS
    assert ws.cell(TEMPLATE_DATA_START, 1).value == 1
    assert ws.cell(TEMPLATE_DATA_START + TEMPLATE_DATA_ROWS - 1, 1).value == TEMPLATE_DATA_ROWS
    assert ws.cell(TEMPLATE_DATA_START, 7).number_format == "DD.MM.YYYY"
    assert ws.cell(TEMPLATE_DATA_START, 8).number_format == "DD.MM.YYYY"
    assert not list(ws.tables)
    assert not ws.data_validations.dataValidation
    assert ws.freeze_panes == f"A{TEMPLATE_DATA_START}"
    wb.close()


def test_filled_template_roundtrip():
    raw = build_import_template_xlsx()
    wb = load_workbook(BytesIO(raw))
    ws = wb[TEMPLATE_SHEET_NAME]
    ws.cell(TEMPLATE_DATA_START, 2, "Ali Veli")
    ws.cell(TEMPLATE_DATA_START, 3, "12345678901")
    ws.cell(TEMPLATE_DATA_START, 4, "Kaynakçı")
    ws.cell(TEMPLATE_DATA_START, 5, "Üretim")
    ws.cell(TEMPLATE_DATA_START, 7, date(2024, 1, 15))
    ws.cell(TEMPLATE_DATA_START, 9, "Yok")
    ws.cell(TEMPLATE_DATA_START + 1, 2, "Ayşe Yılmaz")
    ws.cell(TEMPLATE_DATA_START + 1, 4, "Operatör")
    ws.cell(TEMPLATE_DATA_START + 1, 9, "Engelli")
    ws.cell(TEMPLATE_DATA_START + 1, 8, date(2024, 6, 30))
    buf = BytesIO()
    wb.save(buf)
    wb.close()

    rows = parse_employees_workbook(buf.getvalue())
    assert [row["full_name"] for row in rows] == ["Ali Veli", "Ayşe Yılmaz"]
    assert rows[0]["national_id_masked"] == "12345678901"
    assert rows[0]["job_title"] == "Kaynakçı"
    assert rows[0]["start_date"] == date(2024, 1, 15)
    assert rows[0]["exit_date"] is None
    assert rows[0]["special_status"] is None
    assert rows[1]["special_status"] == "Engelli"
    assert rows[1]["exit_date"] == date(2024, 6, 30)
    assert rows[1]["start_date"] is None


def test_monthly_named_personel_listesi_sheet_is_selected():
    wb = Workbook()
    decoy = wb.active
    decoy.title = "Ozet"
    decoy.append(["Rastgele", "Başlıklar"])
    decoy.append(["Yüklendi", "Sanılmasın"])
    monthly = wb.create_sheet("EYLÜL 2026 PERSONEL LİSTESİ")
    monthly.append(["#", "Adı Soyadı", "TC Kimlik No", "Görevi", "Engelli/Hükümlü", "Giriş Tarihi", "Çıkış Tarihi"])
    monthly.append([1, "Ayşe Kaya", "12345678901", "İşçi", "", date(2024, 2, 1), None])
    monthly.append([2, "", "", "", "", "", ""])
    buf = BytesIO()
    wb.save(buf)
    wb.close()

    rows = parse_employees_workbook(buf.getvalue())
    assert [row["full_name"] for row in rows] == ["Ayşe Kaya"]
    assert rows[0]["job_title"] == "İşçi"
    assert rows[0]["start_date"] == date(2024, 2, 1)


def test_blank_cells_parse_as_none_without_touching_filled_fields():
    wb = Workbook()
    ws = wb.active
    ws.append(["Adı Soyadı", "TC Kimlik No", "Görevi", "Engelli/Hükümlü", "Giriş Tarihi", "Çıkış Tarihi"])
    ws.append(["Eksik Bilgi", None, "Şoför", None, None, None])
    ws.append(["Dolu Bilgi", "98765432109", None, "Hükümlü", "15.03.2024", None])
    buf = BytesIO()
    wb.save(buf)
    wb.close()

    rows = parse_employees_workbook(buf.getvalue())
    assert rows[0]["full_name"] == "Eksik Bilgi"
    assert rows[0]["national_id_masked"] is None
    assert rows[0]["job_title"] == "Şoför"
    assert rows[0]["special_status"] is None
    assert rows[0]["start_date"] is None
    assert rows[1]["special_status"] == "Hükümlü"
    assert rows[1]["start_date"] == date(2024, 3, 15)
    assert rows[1]["job_title"] is None


def test_legacy_simple_workbook_still_imports():
    wb = Workbook()
    ws = wb.active
    ws.append(["Adı Soyadı", "TC Kimlik", "Görevi", "İşe Giriş Tarihi", "Engelli/Hükümlü Durumu"])
    ws.append(["Ali Veli", "12345678901", "Kaynakçı", "2024-01-15", ""])
    buf = BytesIO()
    wb.save(buf)
    wb.close()
    rows = parse_employees_workbook(buf.getvalue())
    assert rows[0]["full_name"] == "Ali Veli"
    assert rows[0]["job_title"] == "Kaynakçı"


def test_numeric_tc_suffix_is_removed_from_personnel_import():
    wb = Workbook()
    ws = wb.active
    ws.append(["Adı Soyadı", "TC Kimlik"])
    ws.append(["Ali Veli", 26230266894.0])
    buf = BytesIO()
    wb.save(buf)
    wb.close()

    rows = parse_employees_workbook(buf.getvalue())
    assert rows[0]["national_id_masked"] == "26230266894"
