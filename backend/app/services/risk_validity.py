"""Risk değerlendirmesi belge geçerliliği ve yenileme takibi.

İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği md.12: risk
değerlendirmesi, tehlike sınıfına göre en fazla az tehlikeli işyerlerinde
6, tehlikeli işyerlerinde 4, çok tehlikeli işyerlerinde 2 yılda bir
yenilenir. Ayrıca işyerinin taşınması/değişmesi, yeni teknoloji veya
ekipman, iş kazası / meslek hastalığı ve ölçüm sonuçlarındaki değişiklik
gibi durumlarda süre beklenmeden yenilenmesi gerekir (md.12/2).

Bu modül yalnızca hesap yapar; kayıt yazmaz.
"""
from __future__ import annotations

from datetime import date

RENEWAL_YEARS: dict[str, int] = {
    "Az Tehlikeli": 6,
    "Tehlikeli": 4,
    "Çok Tehlikeli": 2,
}

# Yenileme tarihine bu kadar gün kalınca "yaklaşıyor" sayılır (planlama payı).
DUE_SOON_DAYS = 90

from app.services.risk_methods import method_label

METHOD_LABEL = "5x5 Matris (L Tipi) — Risk Skoru = Olasılık × Şiddet"

RENEWAL_TRIGGERS = (
    "İşyerinin taşınması veya yapısal değişiklik",
    "Yeni makine, ekipman veya teknoloji kullanılmaya başlanması",
    "Üretim yöntemi veya iş organizasyonu değişikliği",
    "İş kazası, meslek hastalığı veya ramak kala olayı",
    "Ortam ölçümü / sağlık gözetimi sonuçlarında değişiklik",
)

_ALIASES = {
    "az tehlikeli": "Az Tehlikeli",
    "tehlikeli": "Tehlikeli",
    "cok tehlikeli": "Çok Tehlikeli",
    "çok tehlikeli": "Çok Tehlikeli",
}


def normalize_hazard_class(value: str | None) -> str | None:
    """Bilinmeyen/boş sınıf için None döner — sessizce varsayım yapmaz."""
    raw = (value or "").strip()
    if not raw:
        return None
    key = raw.casefold().replace("ı", "i")
    return _ALIASES.get(key) or (raw if raw in RENEWAL_YEARS else None)


def renewal_years(hazard_class: str | None) -> int | None:
    normalized = normalize_hazard_class(hazard_class)
    return RENEWAL_YEARS.get(normalized) if normalized else None


def add_years(start: date, years: int) -> date:
    """29 Şubat gibi kenar durumlarda 28 Şubat'a çeker."""
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        return start.replace(year=start.year + years, day=28)


def build_validity(
    *,
    hazard_class: str | None,
    assessment_date: date | None,
    fallback_date: date | None = None,
    today: date | None = None,
    method_code: str | None = None,
) -> dict:
    """Belge geçerlilik durumu.

    `assessment_date` kayıtlı belge tarihi; yoksa `fallback_date` (ilk risk
    kaydının tarihi) tahmini olarak kullanılır ve kaynak "estimated" olur.
    """
    now = today or date.today()
    years = renewal_years(hazard_class)
    effective = assessment_date or fallback_date
    source = "recorded" if assessment_date else ("estimated" if fallback_date else "missing")
    method = method_label(method_code) if method_code else METHOD_LABEL

    out: dict = {
        "hazard_class": normalize_hazard_class(hazard_class),
        "hazard_class_raw": (hazard_class or None),
        "renewal_years": years,
        "assessment_date": effective.isoformat() if effective else None,
        "assessment_date_source": source,
        "valid_until": None,
        "days_left": None,
        "status": "unknown",
        "message": "",
        "method": method,
        "method_code": method_code or "5x5_l",
        "renewal_triggers": list(RENEWAL_TRIGGERS),
    }

    if years is None:
        out["message"] = (
            "İşyerinin tehlike sınıfı girilmediği için yenileme süresi hesaplanamıyor. "
            "İşyeri kartında tehlike sınıfını seçin."
        )
        return out
    if effective is None:
        out["message"] = (
            f"Risk değerlendirmesi tarihi girilmemiş. Bu işyeri {years} yılda bir "
            "yenileme kapsamındadır; belge tarihini girince yenileme takibi başlar."
        )
        return out

    valid_until = add_years(effective, years)
    days_left = (valid_until - now).days
    out["valid_until"] = valid_until.isoformat()
    out["days_left"] = days_left

    pretty = valid_until.strftime("%d.%m.%Y")
    if days_left < 0:
        out["status"] = "expired"
        out["message"] = (
            f"Risk değerlendirmesinin geçerlilik süresi {pretty} tarihinde doldu "
            f"({abs(days_left)} gün geçti). Yenilenmesi zorunlu."
        )
    elif days_left <= DUE_SOON_DAYS:
        out["status"] = "due_soon"
        out["message"] = (
            f"Risk değerlendirmesi {pretty} tarihinde yenilenmeli — {days_left} gün kaldı."
        )
    else:
        out["status"] = "ok"
        out["message"] = (
            f"Risk değerlendirmesi {pretty} tarihine kadar geçerli "
            f"(tehlike sınıfı: {out['hazard_class']}, {years} yıl)."
        )
    if source == "estimated":
        out["message"] += " Tarih, ilk risk kaydından tahmin edildi; belge tarihini girmeniz önerilir."
    return out


def _fmt(value: date | str | None) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime("%d.%m.%Y")


def document_meta_rows(
    *,
    validity: dict | None = None,
    prepared_by: str | None = None,
    workplace_physician: str | None = None,
    employer_representative: str | None = None,
    employee_representative: str | None = None,
    support_staff: str | None = None,
    document_no: str | None = None,
    revision_no: str | None = None,
    revision_reason: str | None = None,
) -> list[tuple[str, str]]:
    """Rapor başlığındaki mevzuat künyesi (yöntem + ekip + geçerlilik + belge kontrolü)."""
    validity = validity or {}
    rows: list[tuple[str, str]] = [
        ("Belge No", document_no or "—"),
        ("Revizyon No", revision_no or "00"),
        ("Kullanılan Yöntem", validity.get("method") or METHOD_LABEL),
        ("Değerlendirme Tarihi", _fmt(validity.get("assessment_date"))),
        ("Geçerlilik / Yenileme Tarihi", _fmt(validity.get("valid_until"))),
    ]
    years = validity.get("renewal_years")
    if years:
        rows.append(("Yenileme Periyodu", f"{years} yıl (tehlike sınıfı gereği)"))
    if revision_reason:
        rows.append(("Revizyon Nedeni", revision_reason))
    rows.extend(
        [
            ("İSG Uzmanı / Hazırlayan", prepared_by or "—"),
            ("İşyeri Hekimi", workplace_physician or "—"),
            ("İşveren / İşveren Vekili", employer_representative or "—"),
            ("Çalışan Temsilcisi", employee_representative or "—"),
            ("Destek Elemanı", support_staff or "—"),
        ]
    )
    return rows
