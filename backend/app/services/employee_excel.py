# -*- coding: utf-8 -*-
"""Personel Excel içe aktarma — esnek başlık + şablon."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook


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
    "engellihukumludurumu": "special_status",
    "engellihukumlu": "special_status",
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


def parse_employees_workbook(content: bytes) -> list[dict]:
    wb = load_workbook(BytesIO(content), data_only=True)
    try:
        ws = wb.active
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

    # İlk 30 satırda başlık ara
    header_idx = None
    field_map: dict[int, str] = {}
    for i, row in enumerate(rows_raw[:30]):
        mapping = {idx: map_header(v) for idx, v in enumerate(row)}
        mapping = {k: v for k, v in mapping.items() if v}
        has_name = "full_name" in mapping.values() or (
            "_first" in mapping.values() and "_last" in mapping.values()
        )
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
                tc = _cell(raw)
                item["national_id_masked"] = tc or None
            elif key == "job_title":
                item["job_title"] = _cell(raw) or None
            elif key == "department":
                item["department"] = _cell(raw) or None
            elif key == "start_date":
                item["start_date"] = _parse_date(raw)
            elif key == "special_status":
                item["special_status"] = _cell(raw) or None
        if not item["full_name"]:
            item["full_name"] = " ".join(p for p in (first, last) if p).strip()
        if not item["full_name"]:
            continue
        if map_header(item["full_name"]):
            continue
        out.append(item)
    return out


TEMPLATE_HEADERS = [
    "Adı Soyadı",
    "TC Kimlik",
    "Görevi",
    "İşe Giriş Tarihi",
    "Engelli/Hükümlü Durumu",
]

TEMPLATE_EXAMPLE = [
    "Ali Veli",
    "12345678901",
    "Kaynakçı",
    "2024-01-15",
    "",
]


def build_import_template_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Personel"
    ws.append(TEMPLATE_HEADERS)
    ws.append(TEMPLATE_EXAMPLE)
    ws.append(["Ayşe Yılmaz", "", "Operatör", "15.03.2023", "Engelli"])
    note = wb.create_sheet("Aciklama")
    note.append(["Sütun", "Zorunlu", "Açıklama"])
    note.append(["Adı Soyadı", "Evet", "Personelin adı ve soyadı"])
    note.append(["TC Kimlik", "Hayır", "11 hane; boş bırakılabilir"])
    note.append(["Görevi", "Hayır", "Branş / görev / unvan"])
    note.append(["İşe Giriş Tarihi", "Hayır", "YYYY-AA-GG veya GG.AA.YYYY"])
    note.append(["Engelli/Hükümlü Durumu", "Hayır", "Örn: Engelli, Hükümlü, boş"])
    note.append([])
    note.append(["Not", "", "1. satır başlıkları silmeyin. Örnek satırları silip kendi listenizi yazın."])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
