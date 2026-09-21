# -*- coding: utf-8 -*-
"""Personel Excel içe aktarma — esnek başlık + şablon."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.services.national_id_format import normalize_national_id


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    text = str(v).strip().replace("\ufeff", "").replace("\xa0", " ").strip()
    return "" if text.lower() in ("none", "nan") else text


def _norm(text: str) -> str:
    t = _cell(text).strip()
    t = t.replace("İ", "i").replace("I", "i").replace("ı", "i")
    t = t.lower().replace("ı", "i")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    for a, b in (
        (" ", ""),
        ("_", ""),
        ("-", ""),
        (".", ""),
        ("/", ""),
        ("\\", ""),
        ("ğ", "g"),
        ("ü", "u"),
        ("ş", "s"),
        ("ö", "o"),
        ("ç", "c"),
        ("*", ""),
    ):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "", t)


_HEADER_ALIASES: dict[str, str] = {
    "adsoyad": "full_name",
    "adisoyadi": "full_name",
    "adsoyadi": "full_name",
    "adivesoyadi": "full_name",
    "advesoyad": "full_name",
    "isimsoyisim": "full_name",
    "isimsoyad": "full_name",
    "namesurname": "full_name",
    "fullname": "full_name",
    "isim": "full_name",
    "personeladisoyadi": "full_name",
    "personeladsoyad": "full_name",
    "calisanadisoyadi": "full_name",
    "calisanadsoyad": "full_name",
    "tc": "national_id_masked",
    "tckimlik": "national_id_masked",
    "tckimlikno": "national_id_masked",
    "tckimliknumarasi": "national_id_masked",
    "tcno": "national_id_masked",
    "tckn": "national_id_masked",
    "kimlik": "national_id_masked",
    "kimlikno": "national_id_masked",
    "gorev": "job_title",
    "gorevi": "job_title",
    "bransgorev": "job_title",
    "bransgorevi": "job_title",
    "unvan": "job_title",
    "unvani": "job_title",
    "meslek": "job_title",
    "pozisyon": "job_title",
    "isegiristarihi": "start_date",
    "isegiris": "start_date",
    "giristarihi": "start_date",
    "baslangictarihi": "start_date",
    "startdate": "start_date",
    "istencikistarihi": "exit_date",
    "cikistarihi": "exit_date",
    "istenayrilmatarihi": "exit_date",
    "exitdate": "exit_date",
    "engellihukumludurumu": "special_status",
    "engellihukumlu": "special_status",
    "engellihukumludurum": "special_status",
    "ozeldurum": "special_status",
    "specialstatus": "special_status",
    "departman": "department",
    "bolum": "department",
    "bolumu": "department",
    "birim": "department",
}


def map_header(value: Any) -> str:
    n = _norm(str(value or ""))
    if not n:
        return ""
    if n in _HEADER_ALIASES:
        return _HEADER_ALIASES[n]
    if "soyad" in n and ("ad" in n or "isim" in n or "personel" in n or "calisan" in n):
        return "full_name"
    if n in ("ad", "adi"):
        return "_first"
    if n in ("soyad", "soyadi"):
        return "_last"
    if "tc" in n or "kimlik" in n:
        return "national_id_masked"
    if "gorev" in n or "unvan" in n or "meslek" in n:
        return "job_title"
    if "giris" in n and "tarih" in n:
        return "start_date"
    if ("cikis" in n or "ayrilma" in n) and "tarih" in n:
        return "exit_date"
    if "engelli" in n or "hukumlu" in n or "ozeldurum" in n:
        return "special_status"
    if "departman" in n or n == "bolum" or n == "bolumu":
        return "department"
    return ""


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _cell(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _personnel_sheet(wb):
    # Kullanıcı dosyaları aylık adlandırılabiliyor ("EYLÜL 2026 PERSONEL LİSTESİ").
    for name in wb.sheetnames:
        if _norm(name) == "personel":
            return wb[name]
    for name in wb.sheetnames:
        if "personel" in _norm(name):
            return wb[name]
    return wb.active


def _is_placeholder_name(value: str) -> bool:
    n = _norm(value)
    return n in {
        "ornek",
        "orneksatir",
        "ornekpersonel",
        "adisoyadiyaziniz",
        "adsoyadyaziniz",
        "ornek1",
        "ornek2",
    }


def _normalize_special_status(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    n = _norm(text)
    if n in {"yok", "hayir", "degil", "-", "bos", "yoktur"}:
        return None
    if n in {"engelli"}:
        return "Engelli"
    if n in {"hukumlu"}:
        return "Hükümlü"
    if n in {"engellivehukumlu", "engellihukumlu"}:
        return "Engelli ve Hükümlü"
    return text[:80]


def parse_employees_workbook(content: bytes) -> list[dict]:
    wb = load_workbook(BytesIO(content), data_only=True)
    try:
        ws = _personnel_sheet(wb)
        rows_raw: list[list[Any]] = []
        for row in ws.iter_rows(values_only=True):
            vals = list(row)
            while vals and not _cell(vals[-1]):
                vals.pop()
            if any(_cell(v) for v in vals):
                rows_raw.append(vals)
    finally:
        wb.close()
    if not rows_raw:
        return []

    # İlk 30 satırda gerçek sütun başlığını ara (banner/açıklama satırlarını atla).
    header_idx = None
    field_map: dict[int, str] = {}
    for i, row in enumerate(rows_raw[:30]):
        mapping = {idx: map_header(v) for idx, v in enumerate(row)}
        mapping = {k: v for k, v in mapping.items() if v}
        mapped = set(mapping.values())
        has_name = "full_name" in mapped or ("_first" in mapped and "_last" in mapped)
        if has_name:
            header_idx = i
            field_map = mapping
            break
    if header_idx is None:
        raise ValueError(
            "Excel dosyasında 'Adı Soyadı' (veya Adı + Soyadı) sütunu bulunmalıdır. "
            "Şablonu indirip aynı başlıklarla doldurun."
        )

    out: list[dict] = []
    for row in rows_raw[header_idx + 1 :]:
        item = {
            "full_name": "",
            "national_id_masked": None,
            "job_title": None,
            "department": None,
            "start_date": None,
            "exit_date": None,
            "special_status": None,
        }
        first = last = ""
        for idx, key in field_map.items():
            raw = row[idx] if idx < len(row) else None
            if key == "_first":
                first = _cell(raw)
            elif key == "_last":
                last = _cell(raw)
            elif key == "full_name":
                item["full_name"] = _cell(raw)
            elif key == "national_id_masked":
                tc = normalize_national_id(_cell(raw))
                item["national_id_masked"] = tc or None
            elif key == "job_title":
                item["job_title"] = _cell(raw) or None
            elif key == "department":
                item["department"] = _cell(raw) or None
            elif key == "start_date":
                item["start_date"] = _parse_date(raw)
            elif key == "exit_date":
                item["exit_date"] = _parse_date(raw)
            elif key == "special_status":
                item["special_status"] = _normalize_special_status(_cell(raw))
        if not item["full_name"]:
            item["full_name"] = " ".join(p for p in (first, last) if p).strip()
        if not item["full_name"]:
            continue
        if map_header(item["full_name"]) or _is_placeholder_name(item["full_name"]):
            continue
        out.append(item)
    return out


TEMPLATE_HEADERS = [
    "#",
    "Adı Soyadı",
    "TC Kimlik No",
    "Görevi",
    "Engelli/Hükümlü",
    "Giriş Tarihi",
    "Çıkış Tarihi",
]

TEMPLATE_SHEET_NAME = "PERSONEL LİSTESİ"
TEMPLATE_DATA_START = 2
TEMPLATE_DATA_ROWS = 90
SPECIAL_STATUS_CHOICES = ("Yok", "Engelli", "Hükümlü", "Engelli ve Hükümlü")

_BORDER = "000000"
_THIN = Side(style="thin", color=_BORDER)
_CELL_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_FONT_NAME = "Calibri"
_FONT_SIZE = 10


def _style_header_cell(cell, *, required: bool = False) -> None:
    cell.font = Font(bold=True, name=_FONT_NAME, size=_FONT_SIZE)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = _CELL_BORDER
    if required:
        cell.fill = PatternFill("solid", fgColor="FEF3C7")


def build_import_template_xlsx() -> bytes:
    """Kullanıcı şablonunun birebir kopyası: tek sayfa, 1. satır başlık, 90 numaralı satır.

    Sütun düzeni: # | Adı Soyadı | TC Kimlik No | Görevi | Engelli/Hükümlü |
    Giriş Tarihi | Çıkış Tarihi. Tarih sütunları GG.AA.YYYY biçimlidir; hiçbir
    hücrede giriş engelleyen doğrulama/dropdown yoktur.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = TEMPLATE_SHEET_NAME
    last_col = get_column_letter(len(TEMPLATE_HEADERS))
    last_data = TEMPLATE_DATA_START + TEMPLATE_DATA_ROWS - 1

    for idx, title in enumerate(TEMPLATE_HEADERS, start=1):
        cell = ws.cell(1, idx, title)
        _style_header_cell(cell, required=(idx == 2))

    for row_idx in range(TEMPLATE_DATA_START, last_data + 1):
        seq_cell = ws.cell(row_idx, 1, row_idx - TEMPLATE_DATA_START + 1)
        seq_cell.number_format = "###"
        for col_idx in range(1, len(TEMPLATE_HEADERS) + 1):
            cell = ws.cell(row_idx, col_idx)
            cell.border = _CELL_BORDER
            cell.font = Font(name=_FONT_NAME, size=_FONT_SIZE)
            if col_idx in (1, 3):
                cell.number_format = "###"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in (6, 7):
                cell.number_format = "DD.MM.YYYY"
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(vertical="center")

    widths = {1: 3.11, 2: 25.55, 3: 13.0, 4: 14.78, 6: 11.44, 7: 11.22}
    for col_idx, width in widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.freeze_panes = f"A{TEMPLATE_DATA_START}"
    ws.auto_filter.ref = f"A1:{last_col}1"
    ws.print_title_rows = "1:1"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
