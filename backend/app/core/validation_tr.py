"""API doğrulama (422) hatalarını Türkçe ve alan adıyla döndür."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

FIELD_LABELS: dict[str, str] = {
    "company_id": "Firma",
    "branch_id": "Şube",
    "event_type": "Olay tipi",
    "short_summary": "Kısa özet",
    "event_date": "Olay tarihi",
    "event_time": "Saat",
    "department": "Departman",
    "location": "Olay yeri",
    "area": "Alan",
    "work_being_done": "Yapılan iş",
    "related_people": "İlgili kişiler",
    "witness_names": "Şahit isimleri",
    "equipment_used": "Kullanılan ekipman",
    "chemical_used": "Kullanılan kimyasal",
    "detail": "Detay",
    "classification": "Sınıflandırma",
    "probability": "Olasılık",
    "severity": "Şiddet",
    "risk_analysis_status": "Risk analizi durumu",
    "risk_analysis_note": "Risk analizi notu",
    "emergency_relation": "Acil durum ilişkisi",
    "emergency_note": "Acil durum notu",
    "evaluation_text": "Değerlendirme",
    "recorded_by_name": "Kaydeden",
    "safety_specialist": "İSG uzmanı",
    "workplace_physician": "İşyeri hekimi",
    "employer_representative": "İşveren / vekili",
    "sgk_report_date": "SGK bildirim tarihi",
    "accident_type": "Kaza tipi",
    "injury_type": "Yaralanma tipi",
    "intervention_detail": "Müdahale detayı",
    "report_days": "Rapor günü",
    "status": "Durum",
    "full_name": "Ad soyad",
    "email": "E-posta",
    "password": "Şifre",
    "phone": "Telefon",
    "name": "Ad",
    "title": "Başlık",
    "description": "Açıklama",
    "address": "Adres",
    "authorized_person": "Yetkili kişi",
    "sgk_registry_no": "SGK sicil no",
    "instructor_name": "Eğitmen",
    "activity": "Faaliyet",
    "year": "Yıl",
    "month": "Ay",
    "planned_date": "Planlanan tarih",
    "visit_date": "Ziyaret tarihi",
    "subject": "Konu",
    "notes": "Notlar",
    "start_date": "Başlangıç tarihi",
    "end_date": "Bitiş tarihi",
    "valid_from": "Geçerlilik başlangıcı",
    "valid_until": "Geçerlilik bitişi",
    "exam_date": "Muayene tarihi",
    "next_exam_date": "Sonraki muayene",
    "physician_name": "Hekim",
    "summary": "Özet",
    "osgb_id": "OSGB",
    "professional_id": "Profesyonel",
    "employee_id": "Personel",
}


def field_label(name: str) -> str:
    return FIELD_LABELS.get(name, name.replace("_", " "))


def translate_msg(err: dict) -> str:
    etype = err.get("type") or ""
    ctx = err.get("ctx") or {}
    msg = str(err.get("msg") or "")

    # Özel ValueError mesajları zaten Türkçe olabilir
    if etype == "value_error" and msg:
        cleaned = msg.replace("Value error, ", "").strip()
        if cleaned and not cleaned.lower().startswith("value error"):
            return cleaned

    if etype in {"missing", "missing_argument"}:
        return "bu alan zorunludur"
    if etype == "string_too_short":
        mn = ctx.get("min_length")
        return f"en az {mn} karakter olmalıdır" if mn is not None else "çok kısa"
    if etype == "string_too_long":
        mx = ctx.get("max_length")
        return f"en fazla {mx} karakter olabilir" if mx is not None else "çok uzun"
    if etype in {"too_short", "too_long"} and "min_length" in ctx:
        return f"en az {ctx['min_length']} karakter olmalıdır"
    if etype.startswith("greater_than"):
        return f"en az {ctx.get('ge', ctx.get('gt', ''))} olmalıdır"
    if etype.startswith("less_than"):
        return f"en fazla {ctx.get('le', ctx.get('lt', ''))} olabilir"
    if etype in {"int_parsing", "int_type"}:
        return "geçerli bir sayı giriniz"
    if etype in {"float_parsing", "float_type"}:
        return "geçerli bir sayı giriniz"
    if etype in {"bool_parsing", "bool_type"}:
        return "geçerli bir evet/hayır değeri giriniz"
    if etype in {"date_parsing", "date_type", "date_from_datetime_parsing"}:
        return "geçerli bir tarih giriniz (YYYY-AA-GG)"
    if etype in {"datetime_parsing", "datetime_type"}:
        return "geçerli bir tarih-saat giriniz"
    if etype in {"enum", "literal_error"}:
        return "geçersiz seçim"
    if etype == "string_type":
        return "metin giriniz"
    if "email" in etype:
        return "geçerli bir e-posta adresi giriniz"
    if msg.lower().startswith("string should have at least"):
        # İngilizce pydantic yedek
        parts = msg.split()
        n = next((p for p in parts if p.isdigit()), None)
        return f"en az {n} karakter olmalıdır" if n else "metin çok kısa"
    if msg.lower().startswith("string should have at most"):
        parts = msg.split()
        n = next((p for p in parts if p.isdigit()), None)
        return f"en fazla {n} karakter olabilir" if n else "metin çok uzun"
    if "field required" in msg.lower():
        return "bu alan zorunludur"
    return msg or "geçersiz değer"


def format_validation_errors(errors: list[dict]) -> str:
    parts: list[str] = []
    for err in errors:
        loc = [x for x in (err.get("loc") or ()) if x not in ("body", "query", "path", "header")]
        field = str(loc[-1]) if loc else "alan"
        if isinstance(loc[-1], int) if loc else False:
            field = str(loc[-2]) if len(loc) >= 2 else "alan"
        parts.append(f"{field_label(str(field))}: {translate_msg(err)}")
    # Tekrarları sadeleştir
    seen: set[str] = set()
    uniq: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return " · ".join(uniq) if uniq else "Girilen bilgiler geçersiz."


def register_turkish_validation(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _tr_validation_handler(_: Request, exc: RequestValidationError):
        detail = format_validation_errors(list(exc.errors()))
        return JSONResponse(status_code=422, content={"detail": detail})
