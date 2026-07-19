"""Sağlık gözetimi yardımcıları — İSG PRO 2026 parity."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

# PRO SAGLIK_MARUZIYET_LISTESI
EXPOSURE_OPTIONS = [
    "Kurşun",
    "Kimyasal",
    "Solvent",
    "Toz",
    "Gürültü",
    "Titreşim",
    "Ergonomi",
    "Yüksekte çalışma",
    "Elektrik",
    "Biyolojik",
    "Radyasyon",
    "Sıcak ortam",
    "Soğuk ortam",
    "Kapalı alan",
    "Gece çalışması",
]

# Meslek → tetkik / maruziyet / periyot (PRO SAGLIK_MESLEK_TETKIK_ONERILERI)
MESLEK_TETKIK: dict[str, dict] = {
    "aku": {
        "label": "Akü / kurşun maruziyeti",
        "tests": ["Kanda kurşun", "Hemogram", "Karaciğer/böbrek fonksiyonları", "İşyeri hekimi değerlendirmesi"],
        "exposures": ["Kurşun", "Kimyasal", "Toz"],
        "period": "Kurşun maruziyetinde işyeri hekimi değerlendirmesine göre biyolojik izlem; uygulamada çoğu işletmede 3 ayda bir takip.",
    },
    "kaynak": {
        "label": "Kaynak / sıcak çalışma",
        "tests": ["Odyometri", "Solunum fonksiyon testi", "Akciğer grafisi", "Göz muayenesi"],
        "exposures": ["Gürültü", "Toz", "Radyasyon"],
        "period": "Kaynak dumanı, gürültü ve göz maruziyeti nedeniyle periyodik sağlık gözetimi planlanmalıdır.",
    },
    "boya": {
        "label": "Boyahane / solvent-kimyasal",
        "tests": ["Solunum fonksiyon testi", "Akciğer grafisi", "Karaciğer fonksiyonları", "Kimyasal maruziyet değerlendirmesi"],
        "exposures": ["Kimyasal", "Solvent", "Toz"],
        "period": "Solvent ve kimyasal maruziyet düzeyine göre takip periyodu işyeri hekimi tarafından belirlenir.",
    },
    "forklift": {
        "label": "Forklift / araç-operatör",
        "tests": ["Göz muayenesi", "Odyometri", "Psikoteknik/operatör belge kontrolü", "Genel sağlık değerlendirmesi"],
        "exposures": ["Titreşim", "Gürültü"],
        "period": "Operatörlerde görme, işitme ve dikkat gerektiren çalışmalar için uygunluk düzenli takip edilmelidir.",
    },
    "vinc": {
        "label": "Kaldırma ekipmanı operatörü",
        "tests": ["Göz muayenesi", "Odyometri", "Denge/uygunluk değerlendirmesi", "Genel sağlık değerlendirmesi"],
        "exposures": ["Yüksekte çalışma", "Gürültü"],
        "period": "Kaldırma ekipmanı operatörlerinde görme, işitme ve dikkat gerektiren sağlık uygunluğu izlenmelidir.",
    },
    "elektrik": {
        "label": "Elektrik bakım / pano",
        "tests": ["Göz muayenesi", "Genel sağlık değerlendirmesi", "Yüksekte çalışma uygunluğu"],
        "exposures": ["Elektrik", "Yüksekte çalışma"],
        "period": "Elektrik çalışmalarında görme, yüksekte çalışma ve genel sağlık uygunluğu değerlendirilmelidir.",
    },
    "toz": {
        "label": "Tozlu ortam / solunum",
        "tests": ["Solunum fonksiyon testi", "Akciğer grafisi", "Toz maruziyet değerlendirmesi"],
        "exposures": ["Toz", "Gürültü"],
        "period": "Tozlu ortamlarda solunum tetkikleri ve ortam ölçümleri birlikte değerlendirilmelidir.",
    },
    "gurultu": {
        "label": "Gürültülü ortam",
        "tests": ["Odyometri", "Kulak-burun-boğaz değerlendirmesi", "KKD uygunluk kontrolü"],
        "exposures": ["Gürültü"],
        "period": "Gürültülü işlerde odyometri takibi ve kulak koruyucu kullanımı birlikte izlenmelidir.",
    },
    "lab": {
        "label": "Laboratuvar / kimyasal",
        "tests": ["Kimyasal maruziyet değerlendirmesi", "Solunum fonksiyon testi", "Biyolojik izlem", "Göz muayenesi"],
        "exposures": ["Kimyasal", "Biyolojik"],
        "period": "Kimyasal ve biyolojik risklere göre tetkikler işyeri hekimi tarafından belirlenmelidir.",
    },
    "ofis": {
        "label": "Ofis / idari işler",
        "tests": ["Ekranlı araçlarla çalışma değerlendirmesi", "Ergonomi değerlendirmesi", "Göz muayenesi"],
        "exposures": ["Ergonomi"],
        "period": "Ofis çalışanlarında ergonomi, ekranlı araç kullanımı ve genel sağlık takibi ön plandadır.",
    },
}

JOB_ALIASES: list[tuple[str, str]] = [
    ("aku", "aku"), ("akü", "aku"), ("kursun", "aku"), ("kurşun", "aku"), ("plaka", "aku"), ("şarj", "aku"), ("sarj", "aku"),
    ("kaynak", "kaynak"), ("gazaltı", "kaynak"), ("plazma", "kaynak"),
    ("boya", "boya"), ("boyacı", "boya"), ("solvent", "boya"), ("tiner", "boya"),
    ("forklift", "forklift"), ("transpalet", "forklift"), ("operatör", "forklift"), ("şoför", "forklift"), ("sürücü", "forklift"),
    ("vinç", "vinc"), ("vinc", "vinc"), ("caraskal", "vinc"), ("platform", "vinc"),
    ("elektrik", "elektrik"), ("elektrikçi", "elektrik"), ("pano", "elektrik"),
    ("toz", "toz"), ("çimento", "toz"), ("taşlama", "toz"), ("kumlama", "toz"),
    ("gürültü", "gurultu"), ("gurultu", "gurultu"), ("pres", "gurultu"), ("kompresör", "gurultu"),
    ("lab", "lab"), ("laboratuvar", "lab"), ("asit", "lab"),
    ("ofis", "ofis"), ("muhasebe", "ofis"), ("idari", "ofis"), ("büro", "ofis"),
]


def _norm(value: str | None) -> str:
    s = (value or "").casefold()
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c")):
        s = s.replace(a, b)
    return " ".join(s.split())


def suggest_for_job(job_title: str | None, department: str | None = None) -> dict:
    text = _norm(f"{job_title or ''} {department or ''}")
    matched: list[str] = []
    tests: list[str] = []
    exposures: list[str] = []
    periods: list[str] = []
    for alias, key in JOB_ALIASES:
        if _norm(alias) in text and key not in matched:
            matched.append(key)
            info = MESLEK_TETKIK[key]
            for t in info["tests"]:
                if t not in tests:
                    tests.append(t)
            for e in info["exposures"]:
                if e not in exposures:
                    exposures.append(e)
            if info.get("period") and info["period"] not in periods:
                periods.append(info["period"])
    if not matched:
        info = MESLEK_TETKIK["ofis"]
        return {
            "matched": ["ofis"],
            "label": info["label"],
            "suggested_tests": info["tests"],
            "exposures": info["exposures"],
            "period_note": info.get("period") or "",
        }
    labels = [MESLEK_TETKIK[k]["label"] for k in matched]
    return {
        "matched": matched,
        "label": " + ".join(labels),
        "suggested_tests": tests,
        "exposures": exposures,
        "period_note": " ".join(periods),
    }


def health_period_years(hazard_class: str | None) -> int:
    h = (hazard_class or "").casefold()
    if "çok" in h or "cok" in h:
        return 1
    if "tehlike" in h and "az" not in h:
        return 3
    return 5


def default_next_exam(exam_date: date, hazard_class: str | None) -> date:
    years = health_period_years(hazard_class)
    try:
        return exam_date.replace(year=exam_date.year + years)
    except ValueError:
        return exam_date + timedelta(days=365 * years)


def evaluate_blood_lead(value: float | None, ref: float | None = None) -> str | None:
    if value is None:
        return None
    limit = ref if ref is not None else 30.0
    if value > limit * 1.5:
        return "kritik"
    if value > limit:
        return "yuksek"
    if value > limit * 0.8:
        return "izlem"
    return "normal"


def lead_status_label(value: float | None) -> tuple[str, str]:
    """PRO saglik_analiz_status."""
    if value is None:
        return ("Eksik", "gray")
    if value >= 45:
        return ("Acil değerlendirme", "red")
    if value >= 40:
        return ("Kritik", "red")
    if value >= 30:
        return ("Yüksek / takip", "orange")
    if value >= 20:
        return ("Yakın takip", "yellow")
    return ("Normal", "green")


def _text_has_follow_keywords(text: str, keys: list[str]) -> bool:
    hay = _norm(text)
    return any(_norm(k) in hay for k in keys)


def smart_summary(record: Any, employee: Any | None = None) -> str:
    """PRO saglik_akilli_ozet — liste/form için kısa özet."""
    parts: list[str] = []
    status = getattr(record, "fitness_status", None)
    st = status.value if hasattr(status, "value") else str(status or "")
    if st == "unfit":
        parts.append("Uygun değil")
    elif st == "conditional":
        parts.append("Kısıtlı")
    elif st == "tracking":
        parts.append("Takipte")
    nxt = getattr(record, "next_examination_date", None)
    if nxt and nxt < date.today():
        parts.append("Muayene gecikti")
    lead_eval = getattr(record, "blood_lead_eval", None)
    if lead_eval in ("yuksek", "kritik"):
        parts.append(f"Kurşun: {lead_eval}")
    elif getattr(record, "blood_lead_value", None) is not None:
        parts.append(f"Pb {record.blood_lead_value}{record.blood_lead_unit or 'µg/dL'}")
    job = (employee.job_title if employee else None) or ""
    dept = (employee.department if employee else None) or ""
    sug = suggest_for_job(job, dept)
    if "aku" in (sug.get("matched") or []) and getattr(record, "blood_lead_value", None) is None:
        parts.append("Kurşun ölçümü eksik")
    if getattr(record, "other_biological_test", None):
        parts.append("Ek biyolojik tetkik var")
    if getattr(record, "report_storage_path", None):
        parts.append("Rapor dosyası")
    return " · ".join(parts) if parts else "—"


def tetkik_summary(record: Any) -> str:
    parts = []
    if getattr(record, "audiometry_date", None) or getattr(record, "audiometry_result", None):
        parts.append("Odyometri")
    if getattr(record, "spirometry_date", None) or getattr(record, "spirometry_result", None):
        parts.append("SFT")
    if getattr(record, "chest_xray_date", None) or getattr(record, "chest_xray_result", None):
        parts.append("Akciğer")
    if getattr(record, "blood_lead_value", None) is not None:
        parts.append(f"Pb:{record.blood_lead_value}")
    return " · ".join(parts) if parts else "—"


def build_analysis_payload(
    records: list[Any],
    employees: dict[int, Any],
    *,
    all_employees: list[Any] | None = None,
) -> dict:
    """PRO saglik_analiz_data + eksik personel."""
    lead_records = []
    odyo_follow = []
    sft_follow = []
    chest_follow = []
    missing_lead = []

    odyo_keys = ["bozuk", "takip", "ileri", "kayip", "kayıp", "uygun degil", "uygun değil"]
    sft_keys = ["bozuk", "takip", "restriksiyon", "obstruksiyon", "obstrüksiyon", "uygun degil", "uygun değil"]
    chest_keys = ["takip", "patoloji", "pnomokonyoz", "pnömokonyoz", "uygun degil", "uygun değil"]

    for r in records:
        emp = employees.get(r.employee_id)
        val = r.blood_lead_value
        row = {
            "id": r.id,
            "employee_id": r.employee_id,
            "employee_name": emp.full_name if emp else f"#{r.employee_id}",
            "job_title": emp.job_title if emp else None,
            "department": emp.department if emp else None,
            "blood_lead_date": r.blood_lead_date.isoformat() if r.blood_lead_date else None,
            "blood_lead_value": val,
            "blood_lead_unit": r.blood_lead_unit or "µg/dL",
            "blood_lead_eval": r.blood_lead_eval,
            "lead_label": lead_status_label(val)[0],
            "lead_tone": lead_status_label(val)[1],
            "examination_date": r.examination_date.isoformat() if r.examination_date else None,
            "smart_summary": smart_summary(r, emp),
        }
        if val is not None:
            lead_records.append(row)

        odyo_text = f"{r.audiometry_result or ''} {r.audiometry_date or ''}"
        sft_text = f"{r.spirometry_result or ''} {r.spirometry_date or ''}"
        chest_text = f"{r.chest_xray_result or ''} {r.chest_xray_date or ''}"
        if _text_has_follow_keywords(odyo_text, odyo_keys):
            odyo_follow.append(row)
        if _text_has_follow_keywords(sft_text, sft_keys):
            sft_follow.append(row)
        if _text_has_follow_keywords(chest_text, chest_keys):
            chest_follow.append(row)

        hay = _norm(
            f"{emp.job_title if emp else ''} {emp.department if emp else ''} "
            f"{r.exposures or ''} {r.suggested_tests or ''}"
        )
        if any(k in hay for k in ("kursun", "aku", "plaka", "sarj")) and val is None:
            missing_lead.append(row)

    total_lead = len(lead_records)

    def pct(n: int) -> float:
        return round(n / total_lead * 100, 1) if total_lead else 0.0

    ranges = [
        {"label": "0–20", "count": sum(1 for x in lead_records if (x["blood_lead_value"] or 0) < 20), "items": [x for x in lead_records if (x["blood_lead_value"] or 0) < 20]},
        {"label": "20–30", "count": sum(1 for x in lead_records if 20 <= (x["blood_lead_value"] or 0) < 30), "items": [x for x in lead_records if 20 <= (x["blood_lead_value"] or 0) < 30]},
        {"label": "30–40", "count": sum(1 for x in lead_records if 30 <= (x["blood_lead_value"] or 0) < 40), "items": [x for x in lead_records if 30 <= (x["blood_lead_value"] or 0) < 40]},
        {"label": "40–45", "count": sum(1 for x in lead_records if 40 <= (x["blood_lead_value"] or 0) < 45), "items": [x for x in lead_records if 40 <= (x["blood_lead_value"] or 0) < 45]},
        {"label": "45+", "count": sum(1 for x in lead_records if (x["blood_lead_value"] or 0) >= 45), "items": [x for x in lead_records if (x["blood_lead_value"] or 0) >= 45]},
    ]
    over30 = [x for x in lead_records if (x["blood_lead_value"] or 0) >= 30]
    over40 = [x for x in lead_records if (x["blood_lead_value"] or 0) >= 40]
    over45 = [x for x in lead_records if (x["blood_lead_value"] or 0) >= 45]

    covered_emp_ids = {r.employee_id for r in records}
    missing_employees = []
    if all_employees is not None:
        for e in all_employees:
            if e.is_active is False:
                continue
            if e.id not in covered_emp_ids:
                missing_employees.append(
                    {
                        "id": e.id,
                        "full_name": e.full_name,
                        "job_title": e.job_title,
                        "department": e.department,
                        "start_date": e.start_date.isoformat() if getattr(e, "start_date", None) else None,
                    }
                )

    return {
        "total_records": len(records),
        "total_employees": len(all_employees or []),
        "total_lead": total_lead,
        "over30": over30,
        "over40": over40,
        "over45": over45,
        "pct30": pct(len(over30)),
        "pct40": pct(len(over40)),
        "pct45": pct(len(over45)),
        "ranges": [{"label": r["label"], "count": r["count"]} for r in ranges],
        "range_details": ranges,
        "odyo_follow": odyo_follow,
        "sft_follow": sft_follow,
        "chest_follow": chest_follow,
        "missing_lead": missing_lead,
        "missing_employees": missing_employees,
        "lead_records": lead_records,
    }
