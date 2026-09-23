"""5x5 risk analysis Excel parser and normalization helpers.

The importer intentionally understands the workbook shape used by the
professional risk report while accepting small header variations. It returns
plain dictionaries so preview can run without touching the database; the API
layer is responsible for tenant checks and persistence.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from app.services.risk_deadlines import imported_deadline


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).replace("\ufeff", "").replace("\xa0", " ").strip()
    return "" if text.lower() in {"none", "nan"} else text


def _norm(value: Any) -> str:
    text = _cell(value).lower().replace("ı", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", text)


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _cell(value).replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
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
    match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", text)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            return None
    return None


def _parse_term_days(value: Any) -> int | None:
    return imported_deadline(_cell(value))["days"]


_HEADER_ALIASES: dict[str, str] = {
    "pn": "source_pn",
    "no": "source_pn",
    "sira": "source_pn",
    "sirano": "source_pn",
    "fotono": "photo_no",
    "fotografno": "photo_no",
    "prosesalan": "process_area",
    "proses": "process_area",
    "alan": "process_area",
    "bolum": "process_area",
    "faaliyet": "activity",
    "isadimi": "activity",
    "riskunsuru": "risk_source",
    "riskkaynak": "risk_source",
    "tehlike": "hazard",
    "tehlikekaynagi": "hazard",
    "olasisoruc": "consequence",
    "olasisonuc": "consequence",
    "muhtemelsonuc": "consequence",
    "mevcutonlemler": "existing_measures",
    "mevcutkorumalar": "existing_measures",
    "alinmasigerekenilaveonlemler": "additional_measures",
    "ilaveonlemler": "additional_measures",
    "ekonlem": "additional_measures",
    "terminsuresi": "term_text",
    "termin": "term_text",
    "termintarihi": "term_text",
    "sorumlu": "responsible",
    "sorumlular": "responsible",
    "ilgilimevzuatdayanagi": "legislation_basis",
    "mevzuatdayanagi": "legislation_basis",
    "mevzuat": "legislation_basis",
    "rp": "source_score",
    "riskpuani": "source_score",
    "riskskoru": "source_score",
    "olasilik": "probability",
    "olasilik15": "probability",
    "siddet": "severity",
    "siddet15": "severity",
    "s": "severity",
    "s15": "severity",
    "o": "probability",
    "o15": "probability",
    "maruzkisisayisi": "exposed_worker_count",
    "maruzkalankisisayisi": "exposed_worker_count",
    "maruzcalisansayisi": "exposed_worker_count",
    "maruzkalancalisansayisi": "exposed_worker_count",
    "etkilenenkisisayisi": "exposed_worker_count",
    "etkilencalisansayisi": "exposed_worker_count",
    "etkilenencalisansayisi": "exposed_worker_count",
    "calisansayisi": "exposed_worker_count",
    "personelsayisi": "exposed_worker_count",
}


def map_header(value: Any) -> str:
    """Map a Turkish source header to the normalized importer field."""
    normalized = _norm(value)
    if not normalized:
        return ""
    if normalized in _HEADER_ALIASES:
        return _HEADER_ALIASES[normalized]
    if normalized.startswith("o") and "5" in normalized:
        return "probability"
    if normalized.startswith("s") and "5" in normalized:
        return "severity"
    if "olasil" in normalized:
        return "probability"
    if "siddet" in normalized:
        return "severity"
    if "mevcut" in normalized and ("onlem" in normalized or "koruma" in normalized):
        return "existing_measures"
    if "ilave" in normalized and "onlem" in normalized:
        return "additional_measures"
    if "mevzuat" in normalized:
        return "legislation_basis"
    return ""


_REQUIRED_HEADER_FIELDS = {
    "process_area",
    "activity",
    "risk_source",
    "hazard",
    "consequence",
    "probability",
    "severity",
}


def _header_mapping(values: list[Any]) -> dict[int, str]:
    mapping = {index: map_header(value) for index, value in enumerate(values)}
    return {index: field for index, field in mapping.items() if field}


def _is_header(mapping: dict[int, str]) -> bool:
    fields = set(mapping.values())
    return len(fields & _REQUIRED_HEADER_FIELDS) >= 5 and {
        "activity",
        "hazard",
        "probability",
        "severity",
    }.issubset(fields)


def _value(values: list[Any], mapping: dict[int, str], field: str) -> str:
    for index, mapped in mapping.items():
        if mapped == field:
            return _cell(values[index] if index < len(values) else None)
    return ""


def _extract_assessment_date(rows: list[list[Any]]) -> date | None:
    for row in rows[:40]:
        for value in row[:12]:
            text = _cell(value)
            folded = _norm(text)
            if "raportarihi" in folded or "degerlendirmetarihi" in folded:
                parsed = _parse_date(text)
                if parsed:
                    return parsed
                match = re.search(r"(\d{1,2}[./-]\d{1,2}[./-]\d{4})", text)
                if match:
                    parsed = _parse_date(match.group(1))
                    if parsed:
                        return parsed
    return None


def _definition(risk_source: str, hazard: str, consequence: str) -> str:
    parts = []
    if risk_source:
        parts.append(f"Risk unsuru: {risk_source}")
    if hazard:
        parts.append(f"Tehlike: {hazard}")
    if consequence:
        parts.append(f"Olası sonuç: {consequence}")
    return "\n".join(parts)[:2000] or "Excel'den aktarılan risk kaydı"


def _fingerprint(item: dict[str, Any]) -> str:
    fields = (
        "source_pn",
        "process_area",
        "activity",
        "risk_source",
        "hazard",
        "consequence",
        "probability",
        "severity",
        "source_score",
        "existing_measures",
        "additional_measures",
        "term_text",
        "responsible",
        "legislation_basis",
        "photo_no",
    )
    raw = "\x1f".join(_cell(item.get(field)) for field in fields)
    # Keep the legacy fingerprint byte-for-byte identical when the source
    # workbook has no exposure column; this prevents an old upload from being
    # imported a second time after the parser learns the optional field.
    if item.get("exposed_worker_count") is not None:
        raw += "\x1fexposed_worker_count\x1f" + _cell(item.get("exposed_worker_count"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def build_import_risk_code(
    company_id: int,
    source_fingerprint: str,
    collision_number: int = 0,
) -> str:
    """Build a stable, globally unique-looking code for an imported row.

    Risk codes are globally unique, while tenant/RLS filtering can hide codes
    belonging to other workplaces from the importer.  A count-based code such
    as ``RSK-0001`` can therefore collide with an existing row.  Deriving the
    code from the company and normalized source row keeps imports independent
    of the visible row count and makes retries deterministic.
    """
    digest = hashlib.sha1(
        f"{company_id}:{source_fingerprint}".encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest().upper()
    if collision_number > 0:
        return f"RSK-{digest[:12]}{collision_number:04d}"
    return f"RSK-{digest[:16]}"


def _is_support_sheet(title: str) -> bool:
    """Exclude workbook documentation and tracking tabs from risk import."""
    normalized = _norm(title)
    support_tokens = (
        "kontrol",
        "duzeltici",
        "mevzuat",
        "fotografekleri",
        "baskikontrol",
        "yoneticiozeti",
        "uyummatrisi",
        "kritikeksik",
        "metodoloji",
        "metodolojivetanimlar",
        "girisvestandartlar",
        "raporbilgiveonay",
    )
    return any(token in normalized for token in support_tokens)


def _selected_worksheets(workbook: Any) -> list[Any]:
    """Choose the canonical risk tab and explicit risk appendices.

    Premium reports often contain both a print-ready tab and a hidden/raw copy
    of the same table, plus DÖF, methodology and control tabs. Importing every
    recognizable table would duplicate the same risk inventory or turn review
    notes into risks, so a named canonical tab wins when present.
    """
    worksheets = list(workbook.worksheets)
    primary_names = {
        "yazdirmayahazirrapor",
        "riskdegerlendirme",
        "riskdegerlendirmetablosu",
        "riskanalizi",
        "riskanalizitablosu",
    }
    primary = next((ws for ws in worksheets if _norm(ws.title) in primary_names), None)
    if primary is not None:
        selected = [primary]
        for worksheet in worksheets:
            normalized = _norm(worksheet.title)
            if worksheet is primary:
                continue
            if "ek" in normalized and "risk" in normalized and ("foto" in normalized or "resim" in normalized):
                selected.append(worksheet)
        return selected
    return [worksheet for worksheet in worksheets if not _is_support_sheet(worksheet.title)]


def infer_category_name(*values: object) -> str:
    """Return a safe existing hazard-library category for an imported row."""
    text = _norm(" ".join(_cell(value) for value in values if value))
    rules = (
        (("biyolojik", "enfeks", "hijyen", "mikrop"), "Biyolojik Riskler"),
        (("psikososyal", "psikolojik", "stres", "mobbing", "vardiya", "gececalisma"), "Psikososyal Riskler"),
        (("ergonom", "elletasima", "kasiskelet", "duruş", "durus", "tekrarl"), "Ergonomik Riskler"),
        (("kimyasal", "kurşun", "kursun", "asit", "solvent", "sds", "zehir", "hidrojen", "gaz", "toz"), "Kimyasal Riskler"),
        (("yangin", "yangın", "patlama", "atex", "parlayici"), "Yangın ve Patlama Riskleri"),
        (("elektrik", "trafo", "gerilim", "kablo"), "Elektrik Riskleri"),
        (("yuksekte", "yüksekte", "iskele", "merdiven"), "Yüksekte Çalışma Riskleri"),
        (("trafik", "araç", "arac", "kantar", "forklift", "sevkiyat", "kamyon"), "Nakliye ve Trafik Riskleri"),
        (("makine", "mekanik", "sikisma", "sıkışma", "pres", "donanim"), "Mekanik Riskler"),
    )
    for terms, category in rules:
        if any(_norm(term) in text for term in terms):
            return category
    return "Fiziksel Riskler"


def parse_risk_workbook(content: bytes, *, filename: str = "") -> dict[str, Any]:
    """Parse all recognizable 5x5 risk sheets without writing anything."""
    if not content:
        raise ValueError("Boş Excel dosyası yüklenemez.")

    workbook = load_workbook(BytesIO(content), data_only=True, read_only=True)
    parsed_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    sheet_counts: list[dict[str, Any]] = []
    report_date: date | None = None
    try:
        for worksheet in _selected_worksheets(workbook):
            header_mapping: dict[int, str] | None = None
            valid_in_sheet = 0
            rows_seen = 0
            early_rows: list[list[Any]] = []
            for row_number, raw_row in enumerate(worksheet.iter_rows(values_only=True), start=1):
                values = list(raw_row)
                if len(early_rows) < 40:
                    early_rows.append(values)
                mapping = _header_mapping(values)
                if _is_header(mapping):
                    header_mapping = mapping
                    continue
                if header_mapping is None:
                    continue
                if not any(_cell(value) for value in values):
                    continue
                rows_seen += 1
                source_pn = _value(values, header_mapping, "source_pn")
                photo_no = _value(values, header_mapping, "photo_no")
                process_area = _value(values, header_mapping, "process_area")
                activity = _value(values, header_mapping, "activity")
                risk_source = _value(values, header_mapping, "risk_source")
                hazard = _value(values, header_mapping, "hazard")
                consequence = _value(values, header_mapping, "consequence")
                probability = _number(_value(values, header_mapping, "probability"))
                severity = _number(_value(values, header_mapping, "severity"))
                source_score = _number(_value(values, header_mapping, "source_score"))
                exposed_worker_count = _number(_value(values, header_mapping, "exposed_worker_count"))
                # Print-ready reports contain signature blocks and page notes
                # below each table. They can populate one mapped column by
                # coincidence, but are not candidate risk rows unless the
                # activity/hazard side of the row has content.
                if not any((process_area, activity, hazard, consequence, probability, severity)):
                    continue
                if not activity or not hazard or probability is None or severity is None:
                    errors.append(
                        f"{worksheet.title}!{row_number}: Faaliyet, tehlike, Olasılık ve Şiddet alanları birlikte bulunmalıdır."
                    )
                    continue
                if not (1 <= probability <= 5 and probability.is_integer() and 1 <= severity <= 5 and severity.is_integer()):
                    errors.append(f"{worksheet.title}!{row_number}: Olasılık ve Şiddet 1–5 tam sayı olmalıdır.")
                    continue
                probability_int = int(probability)
                severity_int = int(severity)
                calculated_score = probability_int * severity_int
                if source_score is not None and source_score != calculated_score:
                    warnings.append(
                        f"{worksheet.title}!{row_number}: RP={_cell(source_score)} ile O×Ş={calculated_score} farklı; uygulama skoru O×Ş olarak korunacak."
                    )
                if source_score is None:
                    source_score = float(calculated_score)
                exposed_worker_count_int = (
                    max(0, min(1_000_000, int(exposed_worker_count)))
                    if exposed_worker_count is not None
                    else None
                )
                term_text = _value(values, header_mapping, "term_text")
                item = {
                    "source_sheet": worksheet.title[:120],
                    "source_row": row_number,
                    "source_pn": source_pn[:40] or None,
                    "photo_no": photo_no[:40] or None,
                    "process_area": process_area[:200] or "İçe Aktarılan Riskler",
                    "activity": activity[:500],
                    "risk_source": risk_source[:250] or None,
                    "hazard": hazard[:250],
                    "consequence": consequence[:2000] or None,
                    "probability": probability_int,
                    "severity": severity_int,
                    "source_score": float(source_score),
                    "exposed_worker_count": exposed_worker_count_int,
                    "existing_measures": _value(values, header_mapping, "existing_measures")[:2000] or None,
                    "additional_measures": _value(values, header_mapping, "additional_measures")[:2000] or None,
                    "term_text": term_text[:250] or None,
                    "term_days_hint": _parse_term_days(term_text),
                    "responsible": _value(values, header_mapping, "responsible")[:1000] or None,
                    "legislation_basis": _value(values, header_mapping, "legislation_basis")[:5000] or None,
                    "risk_definition": _definition(risk_source, hazard, consequence),
                }
                item["fingerprint"] = _fingerprint(item)
                parsed_rows.append(item)
                valid_in_sheet += 1
            report_date = report_date or _extract_assessment_date(early_rows)
            if valid_in_sheet or rows_seen:
                sheet_counts.append(
                    {"sheet": worksheet.title, "valid_rows": valid_in_sheet, "candidate_rows": rows_seen}
                )
    finally:
        workbook.close()

    # Repeated header blocks and copied report sections should not create the
    # same application record twice inside one upload.
    unique_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for item in parsed_rows:
        fingerprint = item["fingerprint"]
        if fingerprint in seen:
            duplicate_count += 1
            continue
        seen.add(fingerprint)
        unique_rows.append(item)

    return {
        "filename": filename or "risk-analizi.xlsx",
        "file_fingerprint": hashlib.sha256(content).hexdigest()[:32],
        "rows": unique_rows,
        "errors": errors[:200],
        "warnings": warnings[:200],
        "duplicate_rows_in_file": duplicate_count,
        "sheet_counts": sheet_counts,
        "metadata": {
            "assessment_date": report_date.isoformat() if report_date else None,
            "method_code": "5x5_l",
            "method_label": "5x5 Matris (L Tipi)",
        },
    }
