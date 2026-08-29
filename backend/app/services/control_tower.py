"""İşyeri Control Tower için read-only ve açıklanabilir skor/öncelik motoru.

Bu servis yalnız mevcut bounded-context sayaçlarını tüketir. Kayıt değiştirmez,
klinik sağlık verisini puanlamaz ve 0-100 skorun neden düştüğünü açıklar.
"""
from __future__ import annotations

from typing import Any, TypedDict


class PriorityItem(TypedDict):
    domain: str
    severity: str
    count: int
    title: str
    reason: str


def _deduction(count: object, unit: int, cap: int) -> int:
    try:
        safe_count = max(0, int(count or 0))
    except (TypeError, ValueError):
        safe_count = 0
    return min(safe_count * unit, cap)


def build_control_tower(
    *,
    contractors: dict[str, Any],
    ptw: dict[str, Any],
    periodic: dict[str, Any],
    actions: dict[str, Any],
    capacity: dict[str, Any],
) -> dict[str, Any]:
    """Return an explainable score and today's attention queue.

    The score is intentionally operational rather than legal-certification
    language. Health is excluded because role-protected clinical/fitness data
    must not be inferred or exposed through a general management score.
    """
    components = {
        "expired_contracts": _deduction(contractors.get("expired_contracts"), 8, 16),
        "expired_contractor_documents": _deduction(contractors.get("expired_documents"), 4, 16),
        "ptw_attention": _deduction(ptw.get("attention"), 4, 16),
        "periodic_overdue": _deduction(periodic.get("overdue"), 6, 18),
        "periodic_due_date_missing": _deduction(periodic.get("due_date_missing"), 2, 6),
        "overdue_actions": _deduction(actions.get("overdue"), 5, 20),
        "open_actions": _deduction(actions.get("open"), 1, 5),
        "capacity_critical": _deduction(capacity.get("critical_assignments"), 10, 10),
        "capacity_warning": _deduction(capacity.get("warning_assignments"), 5, 5),
        "capacity_overloaded": _deduction(capacity.get("overloaded_professionals"), 10, 10),
    }
    total_deduction = min(sum(components.values()), 100)
    score = max(0, 100 - total_deduction)

    if score >= 90:
        band = "İyi"
    elif score >= 75:
        band = "İzlenmeli"
    elif score >= 50:
        band = "Riskli"
    else:
        band = "Kritik"

    queue: list[PriorityItem] = []

    def add(domain: str, severity: str, count: object, title: str, reason: str) -> None:
        try:
            n = max(0, int(count or 0))
        except (TypeError, ValueError):
            n = 0
        if n:
            queue.append({
                "domain": domain,
                "severity": severity,
                "count": n,
                "title": title,
                "reason": reason,
            })

    add("action", "critical", actions.get("overdue"), "Gecikmiş aksiyonları kapat", "Termin tarihi geçmiş açık DÖF/aksiyon bulunuyor.")
    add("capacity", "critical", capacity.get("critical_assignments"), "Hizmet süresi açığını kapat", "Uzman/hekim fiili hizmet süresi yasal ihtiyacın kritik seviyede altında.")
    add("capacity", "critical", capacity.get("overloaded_professionals"), "Profesyonel kapasite aşımını düzelt", "Planlanan aylık yük normal 11.700 dakika kapasiteyi aşıyor.")
    add("contractor", "critical", contractors.get("expired_contracts"), "Süresi biten taşeron sözleşmelerini incele", "Aktif görünen taşeron sözleşmesinin bitiş tarihi geçmiş.")
    add("contractor", "high", contractors.get("expired_documents"), "Taşeron belgelerini yenile", "Geçerlilik tarihi geçmiş aktif taşeron belgesi bulunuyor.")
    add("periodic", "high", periodic.get("overdue"), "Gecikmiş periyodik kontrolleri planla", "Bir veya daha fazla periyodik kontrolün son tarihi geçmiş.")
    add("ptw", "high", ptw.get("attention"), "İş izinlerini gözden geçir", "Onay bekleyen, aktif, askıda veya süresi geçmiş PTW kaydı var.")
    add("capacity", "high", capacity.get("warning_assignments"), "Hizmet süresi riskini izle", "Fiili hizmet süresi hedefin altında ve uyarı bandında.")
    add("periodic", "medium", periodic.get("due_date_missing"), "Periyodik kontrol tarihlerini tamamla", "Sonraki kontrol tarihi girilmemiş kayıt bulunuyor.")
    add("action", "medium", max(0, int(actions.get("open") or 0) - int(actions.get("overdue") or 0)), "Açık aksiyonları takip et", "Henüz gecikmemiş açık DÖF/aksiyonlar mevcut.")

    severity_rank = {"critical": 0, "high": 1, "medium": 2}
    queue.sort(key=lambda item: (severity_rank.get(item["severity"], 9), -item["count"], item["domain"]))

    return {
        "score": score,
        "band": band,
        "score_version": "v1",
        "deduction_total": total_deduction,
        "deductions": components,
        "today_attention": queue[:10],
        "explainable": True,
        "read_only": True,
        "health_scored": False,
        "health_scored_reason": "Sağlık verisi rol korumalıdır; genel yönetim skoruna klinik çıkarım olarak katılmaz.",
    }
