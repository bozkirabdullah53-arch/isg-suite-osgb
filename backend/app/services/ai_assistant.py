"""AI Asistan — karar destek paneli (0.9.245).

aKare "Solamente" benzeri; ücretli AI API olmadan, mevcut İSG Suite
AI servislerini (hazard hint + risk skorlama + Sanal Müfettiş) tek bir
karar-destek öneri motorunda birleştirir.

Kullanım: İSG uzmanı bir faaliyet/metin girer → asistan risk kategorisi,
skor önerisi, foto etiketleri, mevzuat kontrolleri ve önerilen aksiyonları
tek yanıtta sunar.
"""
from __future__ import annotations

from typing import Any

from app.services.ai_hazard_hint import suggest_hazard_from_text
from app.services.ai_mevzuat import build_report as build_mevzuat_report
from app.services.virtual_inspector import inspect_company

ASSISTANT_ENGINE = "assistant-v1"


def suggest(
    *,
    text: str | None = None,
    activity: str | None = None,
    risk_definition: str | None = None,
    company_id: int | None = None,
    db=None,
) -> dict[str, Any]:
    """Serbest metin + opsiyonel şirket denetimi → karar destek önerisi."""
    blob_parts = [p.strip() for p in [text, activity, risk_definition] if p and p.strip()]
    blob = " ".join(blob_parts)

    # 1. Tehlike kategorisi önerisi (mevcut AI hazard hint)
    hazard = suggest_hazard_from_text(blob or "", activity=activity)

    # 2. Risk skor önerisi (olasılık/şiddet/finansal risk)
    risk_suggestion = None
    if hazard.get("matched") and hazard.get("probability_hint"):
        prob = hazard["probability_hint"]
        # Fine-Kinney frekans varsayılan: orta (3), şiddet: olasılık puanından
        risk_suggestion = {
            "suggested_method": "fine_kinney",
            "probability_hint": prob,
            "frequency_hint": 3,
            "severity_hint": max(1, min(5, prob + 1)),
            "note": "Öneri AI hazard hint'ten türetilmiştir; uzman doğrulaması gerekir.",
        }

    # 3. Mevzuat uyum kontrolü (Sanal Müfettiş) — şirket verisi varsa
    compliance = None
    if company_id is not None and db is not None:
        try:
            report = inspect_company(db, company_id)
            compliance = {
                "compliance_score": report.compliance_score,
                "findings_count": len(report.findings),
                "summary": report.summary,
            }
        except Exception:
            compliance = None

    # 4. Mevzuat uzmanı raporu (kanun + yonetmelik + tedbir + ceza)
    mevzuat_report = None
    if hazard.get("matched"):
        try:
            mevzuat_report = build_mevzuat_report(text=blob, hazard_hint=hazard)
        except Exception:
            mevzuat_report = None

    return {
        "engine": ASSISTANT_ENGINE,
        "hazard_hint": hazard,
        "risk_suggestion": risk_suggestion,
        "compliance_preview": compliance,
        "mevzuat_report": mevzuat_report,
        "next_actions": _next_actions(hazard, risk_suggestion, compliance),
    }


def _next_actions(hazard, risk_suggestion, compliance) -> list[str]:
    actions = []
    if hazard.get("matched"):
        actions.append(
            f"Önerilen tehlike kategorisi: {hazard['suggested_category']}. "
            "Risk değerlendirmesini bu kategoriyle oluşturun."
        )
    if hazard.get("suggested_photo_tags"):
        actions.append(
            "Saha fotoğraflarını etiketleyin: "
            + ", ".join(hazard["suggested_photo_tags"])
        )
    if risk_suggestion:
        actions.append(
            f"Fine-Kinney skor önerisi: O={risk_suggestion['probability_hint']}, "
            f"F={risk_suggestion['frequency_hint']}, S={risk_suggestion['severity_hint']}. "
            "Uzman onayıyla netleştirin."
        )
    if compliance and compliance.get("compliance_score", 100) < 80:
        actions.append(
            f"Mevzuat uyum skoru düşük ({compliance['compliance_score']}/100). "
            "Sanal Müfettiş raporunu inceleyin ve düzeltici aksiyonları alın."
        )
    if not actions:
        actions.append("Daha fazla detay girin; faaliyet ve risk tanımı yardımcı olur.")
    return actions
