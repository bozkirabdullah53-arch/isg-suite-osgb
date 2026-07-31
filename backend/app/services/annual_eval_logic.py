"""0.9.135 — Yıllık plan değerlendirme hesapları (plan kayıtlarını değiştirmez)."""
from __future__ import annotations

from datetime import date
from typing import Any

from app.schemas.annual_eval import EXCLUDED_FROM_RATE, OUTCOME_STATUSES, REPORT_STATUSES

OUTCOME_LABELS = {
    "planlandi": "Planlandı",
    "devam": "Devam Ediyor",
    "tamam": "Tamamlandı",
    "kismi": "Kısmen Tamamlandı",
    "gecikmeli_tamam": "Gecikmeli Tamamlandı",
    "ertelendi": "Ertelendi",
    "gerceklesmedi": "Gerçekleştirilmedi",
    "iptal": "İptal Edildi",
    "plan_revizyonuyla_kaldirildi": "Plan Revizyonuyla Kaldırıldı",
}


def validate_outcome_fields(outcome: str, data: dict[str, Any]) -> None:
    if outcome in ("tamam", "gecikmeli_tamam"):
        if not data.get("actual_end"):
            raise ValueError("Tamamlanan faaliyet için gerçekleşme tarihi zorunludur.")
        if not (data.get("result_text") or "").strip():
            raise ValueError("Tamamlanan faaliyet için sonuç açıklaması zorunludur.")
    if outcome == "kismi":
        if data.get("completion_pct") is None:
            raise ValueError("Kısmi tamamlanma için oran zorunludur.")
        if not (data.get("result_text") or "").strip():
            raise ValueError("Kısmi tamamlanma için eksik kalan bölüm açıklaması zorunludur.")
    if outcome == "ertelendi":
        if not (data.get("deviation_reason") or "").strip():
            raise ValueError("Erteleme nedeni zorunludur.")
    if outcome == "gerceklesmedi":
        if not (data.get("deviation_reason") or "").strip():
            raise ValueError("Gerçekleşmeme gerekçesi zorunludur.")
        if not (data.get("next_year_suggestion") or "").strip():
            raise ValueError("Bir sonraki yıl önerisi zorunludur.")
    if outcome == "iptal":
        if not (data.get("deviation_reason") or "").strip():
            raise ValueError("İptal gerekçesi zorunludur.")


def compute_delay_days(target: date | None, actual_end: date | None) -> int | None:
    if not target or not actual_end:
        return None
    return (actual_end - target).days


def item_score(outcome: str, completion_pct: int | None) -> float | None:
    if outcome in EXCLUDED_FROM_RATE:
        return None
    if outcome in ("tamam", "gecikmeli_tamam"):
        return 100.0
    if outcome in ("kismi", "devam"):
        return float(completion_pct if completion_pct is not None else 0)
    return 0.0


def build_kpis(items: list[dict[str, Any]], unplanned_count: int = 0) -> dict[str, Any]:
    total = len(items)
    by = {k: 0 for k in OUTCOME_STATUSES}
    missing_ev = 0
    delayed_done = 0
    scores: list[float] = []
    timed_done = 0
    done_for_time = 0
    evidence_eligible = 0
    evidence_ok = 0
    for it in items:
        st = it.get("outcome_status") or "planlandi"
        by[st] = by.get(st, 0) + 1
        if st not in ("planlandi", "iptal", "plan_revizyonuyla_kaldirildi"):
            evidence_eligible += 1
            if int(it.get("evidence_count") or 0) >= 1:
                evidence_ok += 1
            else:
                missing_ev += 1
        if st == "gecikmeli_tamam" or ((it.get("delay_days") or 0) > 0 and st in ("tamam", "gecikmeli_tamam")):
            delayed_done += 1
        if st in ("tamam", "gecikmeli_tamam"):
            done_for_time += 1
            delay = it.get("delay_days")
            if delay is None or delay <= 0:
                timed_done += 1
        sc = item_score(st, it.get("completion_pct"))
        if sc is not None:
            scores.append(sc)
    rate = round(sum(scores) / len(scores), 1) if scores else None
    on_time = round(100.0 * timed_done / done_for_time, 1) if done_for_time else None
    evidence_rate = round(100.0 * evidence_ok / evidence_eligible, 1) if evidence_eligible else None
    return {
        "planned_total": total,
        "tamam": by.get("tamam", 0),
        "kismi": by.get("kismi", 0),
        "devam": by.get("devam", 0),
        "ertelendi": by.get("ertelendi", 0),
        "gerceklesmedi": by.get("gerceklesmedi", 0),
        "iptal": by.get("iptal", 0),
        "gecikmeli_tamam": by.get("gecikmeli_tamam", 0),
        "missing_evidence": missing_ev,
        "unplanned": unplanned_count,
        "delayed_completed": delayed_done,
        "completion_rate": rate,
        "on_time_rate": on_time,
        "evidence_rate": evidence_rate,
        "formulas": {
            "completion_rate": "Tamam/gecikmeli=%100; kısmi/devam=girilen %; ertelendi/gerçekleşmedi=%0; iptal/revizyon dışı. Plan dışı dahil değil.",
            "on_time_rate": "Tamamlanan faaliyetler içinde gecikme_günleri ≤ 0 olanların oranı.",
            "evidence_rate": "Planlandı/iptal/revizyon dışı kalemlerde en az 1 kanıtı olanların oranı.",
        },
        "note": (
            None
            if rate is not None
            else "Hesaplama için yeterli değerlendirilmiş faaliyet bulunmuyor."
        ),
    }


def meta_payload() -> dict[str, Any]:
    return {
        "engine": "annual-eval-v2",
        "outcomes": [{"code": k, "label": OUTCOME_LABELS.get(k, k)} for k in OUTCOME_STATUSES],
        "report_statuses": list(REPORT_STATUSES),
        "note": (
            "Bu ekran yıllık çalışma planı kalemlerinin gerçekleşmesini değerlendirir; "
            "plan bilgileri burada değiştirilmez. Plan dışı faaliyetler orana girmez."
        ),
    }
