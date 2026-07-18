"""Excel çalışan listesi okuma — eğitim katılımcı aktarımı."""
from __future__ import annotations

import re
from io import BytesIO

from openpyxl import load_workbook


def _cell(v) -> str:
    if v is None:
        return ""
    text = str(v).strip()
    return "" if text.lower() in ("none", "nan") else text


def _norm(text: str) -> str:
    t = _cell(text).lower()
    for a, b in (
        (" ", ""), ("_", ""), ("-", ""), (".", ""),
        ("ı", "i"), ("ğ", "g"), ("ü", "u"), ("ş", "s"), ("ö", "o"), ("ç", "c"),
    ):
        t = t.replace(a, b)
    return t


def _tc_format(tc: str) -> str:
    digits = re.sub(r"\D", "", tc or "")
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}.{digits[9:]}"
    return tc or ""


def _map_headers(headers: list[str]) -> dict[int, str]:
    mapping = {}
    for idx, col in enumerate(headers):
        n = _norm(col)
        if n in ("adsoyad", "adisoyadi", "isim", "ad", "name", "namesurname"):
            mapping[idx] = "full_name"
        elif n in ("tc", "tckimlik", "tckimlikno", "tcno", "kimlik", "kimlikno"):
            mapping[idx] = "national_id_masked"
        elif n in ("bransgorev", "gorevi", "gorev", "pozisyon", "brans", "unvan", "unvani", "jobtitle"):
            mapping[idx] = "job_title"
        elif n in ("bolum", "departman", "birim", "department"):
            mapping[idx] = "department"
    return mapping


def parse_employees_xlsx(content: bytes) -> list[dict]:
    wb = load_workbook(BytesIO(content), data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        vals = list(row)
        while vals and not _cell(vals[-1]):
            vals.pop()
        if any(_cell(v) for v in vals):
            rows.append(vals)
    wb.close()
    if not rows:
        return []

    headers = [_cell(x) for x in rows[0]]
    mapping = _map_headers(headers)
    data_rows = rows[1:]

    # Tek sütun isim listesi
    if not mapping:
        dolu = {i for row in rows for i, v in enumerate(row) if _cell(v)}
        if len(dolu) == 1:
            idx = min(dolu)
            out = []
            for row in rows:
                name = _cell(row[idx] if idx < len(row) else "")
                low = name.lower()
                if not name or any(low.startswith(k) for k in ("sıra", "sira", "no", "ad", "tc", "sertifika")):
                    continue
                out.append({"full_name": name, "national_id_masked": "", "job_title": "", "department": ""})
            return out
        raise ValueError(
            "Excel sütunları okunamadı. Beklenen başlıklar: Ad Soyad, TC Kimlik, Branş/Görev, Bölüm."
        )

    out = []
    for row in data_rows:
        item = {"full_name": "", "national_id_masked": "", "job_title": "", "department": ""}
        for idx, key in mapping.items():
            item[key] = _cell(row[idx] if idx < len(row) else "")
        if not item["full_name"]:
            continue
        if item["national_id_masked"]:
            item["national_id_masked"] = _tc_format(item["national_id_masked"])
        out.append(item)
    return out
