"""Evidence-based advice for the ÇSGB audit readiness card.

This module never changes official records or fabricates evidence. It only turns
existing checklist gaps into actionable guidance and identifies a legally clear
employee-threshold exception for the OHS committee item.
"""
from __future__ import annotations

from typing import Any

ADVICE_VERSION = "csgb-advice-v1"

_ACTIONS: dict[str, tuple[str, str]] = {
    "yetki_belgesi": ("csgb_audit", "OSGB kartında yetki bilgisini tamamlayın"),
    "osgb_kimlik": ("csgb_audit", "OSGB kimlik ve iletişim alanlarını tamamlayın"),
    "profesyonel_kadro": ("professionals", "İSG profesyonelleri ve belge numaralarını tamamlayın"),
    "hizmet_sozlesmesi": ("contracts", "Aktif işyeri hizmet sözleşmesini kaydedin"),
    "gorevlendirme_katip": ("assignments", "İSG-KATİP görevlendirme numarasını tamamlayın"),
    "saha_sure": ("visits", "Saha ziyareti ve çalışma süresi kaydı girin"),
    "tespit_defteri": ("visits", "Ziyarete tespit / öneri defteri kanıtı yükleyin"),
    "kapasite_6331": ("capacity_engine", "Asgari süre ve fiili hizmet dakikalarını kontrol edin"),
    "risk_degerlendirme": ("risk", "Risk değerlendirmesi kaydı oluşturun"),
    "yillik_plan": ("annual_plans", "Yıllık çalışma planını oluşturun"),
    "egitim": ("training", "İSG eğitim kaydı ve katılım belgelerini tamamlayın"),
    "saglik": ("health", "Sağlık gözetimi kayıtlarını tamamlayın"),
    "olay": ("accident", "Sıfır olay beyanını veya olay kayıtlarını belgeleyin"),
    "personel": ("employees", "Aktif çalışan listesini tamamlayın"),
    "periyodik_kontrol": ("periyodik_kontrol", "Ekipman periyodik kontrol sicilini tamamlayın"),
    "acil_durum_plani": ("acil_plan", "Acil durum planı kaydını tamamlayın"),
    "ortam_olcum": ("ortam_olcum", "Risklere göre gerekli ortam ölçümlerini kaydedin"),
    "isg_kurulu": ("isg_kurulu", "Kurul yükümlülüğü ve kayıtlarını kontrol edin"),
    "dokuman_arsiv": ("documents", "Denetim kanıtlarını doküman arşivine yükleyin"),
}


def build_csgb_readiness_advice(
    *,
    missing_items: list[dict[str, Any]] | None,
    active_employees: int,
    company_count: int,
) -> dict[str, Any]:
    """Return non-destructive, evidence-based guidance for current gaps.

    When the complete OSGB scope contains fewer than 50 active employees, no
    individual workplace in that scope can reach the 50-employee threshold.
    Therefore the committee checklist item is flagged for contextual review as
    outside the employee threshold. The official checklist score itself is not
    modified here.
    """
    priorities: list[dict[str, Any]] = []
    contextual_notes: list[dict[str, Any]] = []

    for raw in missing_items or []:
        item = dict(raw)
        code = str(item.get("code") or "")
        module, action = _ACTIONS.get(code, ("csgb_audit", "ÇSGB paketinde kanıtı inceleyin"))
        item["action_module"] = module
        item["action_label"] = action

        if code == "isg_kurulu" and company_count > 0 and active_employees < 50:
            contextual_notes.append(
                {
                    "code": code,
                    "status": "context_review",
                    "title": "İSG kurulu çalışan eşiği",
                    "detail": (
                        f"Sistemde {company_count} aktif işyeri ve toplam {active_employees} aktif çalışan var. "
                        "Hiçbir işyerinin 50 çalışan eşiğine ulaşması mümkün görünmediğinden bu kalem "
                        "çalışan sayısı yönünden kapsam dışı değerlendirilmelidir. Altı aydan fazla süren "
                        "sürekli iş şartı ayrıca işyeri bazında teyit edilmelidir."
                    ),
                    "legal_basis": (
                        "İş Sağlığı ve Güvenliği Kurulları Hakkında Yönetmelik: "
                        "50 ve daha fazla çalışan + altı aydan fazla süren sürekli iş."
                    ),
                }
            )
            item["context_review"] = True
            item["action_label"] = "Çalışan eşiğini doğrulayın; gereksiz eksik sayımını inceleyin"

        priorities.append(item)

    first_actions = [
        {
            "code": item.get("code"),
            "title": item.get("title"),
            "module": item.get("action_module"),
            "action": item.get("action_label"),
        }
        for item in priorities[:5]
    ]

    return {
        "advice_version": ADVICE_VERSION,
        "priority_items": priorities,
        "priority_count": len(priorities),
        "first_actions": first_actions,
        "contextual_notes": contextual_notes,
        "contextual_review_count": len(contextual_notes),
        "score_changed": False,
        "note": "Kayıt üretilmez ve mevcut ÇSGB paket skoru otomatik olarak yükseltilmez.",
    }
