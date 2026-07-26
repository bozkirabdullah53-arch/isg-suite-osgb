"""Pro eğitim Excel/CSV parser smoke tests."""
from app.services.training_excel import parse_employee_upload, parse_employees_xlsx


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_pro_aliases_adivesoyadi():
    content = _xlsx_bytes(
        [
            ["Adı ve Soyadı", "TC Kimlik No", "Görevi", "Bölümü"],
            ["Ali Veli", "12345678901", "Kaynakçı", "Üretim"],
            ["Ayşe Yılmaz", "10987654321", "Operatör", "Paketleme"],
        ]
    )
    rows, meta, logo = parse_employee_upload(content, "liste.xlsx")
    assert len(rows) == 2
    assert rows[0]["full_name"] == "Ali Veli"
    assert "123" in rows[0]["national_id_masked"]
    assert rows[0]["job_title"] == "Kaynakçı"
    assert logo is None
    assert meta == {}


def test_parse_csv_semicolon():
    raw = "Ad Soyad;TC;Görev\nMehmet Demir;11111111110;Teknisyen\n".encode("utf-8-sig")
    rows, _meta, _logo = parse_employee_upload(raw, "liste.csv")
    assert len(rows) == 1
    assert rows[0]["full_name"] == "Mehmet Demir"


def test_parse_employees_xlsx_compat():
    content = _xlsx_bytes([["Ad Soyad"], ["Zeynep Kaya"], ["Canan Su"]])
    rows = parse_employees_xlsx(content)
    assert {r["full_name"] for r in rows} >= {"Zeynep Kaya", "Canan Su"}


def test_turkish_capital_i_header():
    """İ harfi NFKD sonrası adisoyadi olmalı."""
    from app.services.training_excel import _header_field, _norm

    assert _norm("Adı Soyadı") == "adisoyadi"
    assert _norm("ADI SOYADI") == "adisoyadi"
    assert _header_field("Adı Soyadı") == "full_name"
    assert _header_field("Personel Adı ve Soyadı") == "full_name"
    content = _xlsx_bytes(
        [
            ["Adı Soyadı", "Görevi"],
            ["Ali Veli", "Usta"],
            ["Ayşe Fatma", "Operatör"],
        ]
    )
    rows, _, _ = parse_employee_upload(content, "tr.xlsx")
    assert len(rows) == 2
    assert rows[0]["full_name"] == "Ali Veli"


def test_separate_adi_soyadi_columns():
    content = _xlsx_bytes(
        [
            ["Adı", "Soyadı", "Bölüm"],
            ["Mehmet", "Yılmaz", "Kesim"],
            ["Zeynep", "Kaya", "Paket"],
        ]
    )
    rows, _, _ = parse_employee_upload(content, "split.xlsx")
    assert len(rows) == 2
    assert rows[0]["full_name"] == "Mehmet Yılmaz"
    assert rows[1]["full_name"] == "Zeynep Kaya"


def test_header_below_metadata_rows():
    content = _xlsx_bytes(
        [
            ["Eğitimin Adı", "Temel İSG"],
            ["", ""],
            ["Ad Soyad", "Branş/Görev"],
            ["Fatma Nur", "Depocu"],
        ]
    )
    rows, meta, _ = parse_employee_upload(content, "meta.xlsx")
    assert len(rows) == 1
    assert rows[0]["full_name"] == "Fatma Nur"
    assert meta.get("title") == "Temel İSG"
