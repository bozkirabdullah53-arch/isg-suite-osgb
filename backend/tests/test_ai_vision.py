"""Görsel risk analizinde kanıt, özel tehlike eşlemesi ve fail-closed regresyonları."""
from __future__ import annotations

from datetime import date


def test_stair_obstruction_uses_specific_visual_hazard_profile():
    from app.services.ai_vision import _annotate_visual_hazard

    hazard = _annotate_visual_hazard(
        {
            "category": "Fiziksel Riskler",
            "severity": 4,
            "confidence": 0.95,
            "bbox": [0.55, 0.2, 0.3, 0.55],
            "observed": "Merdiven basamakları üzerinde kova ve poşet bırakılmış; geçişi daraltıyor.",
            "note": "Takılma ve düşme riski oluşturuyor.",
            "recommended_ppe": ["genel amaçlı KKD"],
        }
    )

    assert hazard["hazard_key"] == "stair_obstruction"
    assert hazard["hazard_code"] == "MEK-008"
    assert hazard["category"] == "Mekanik Riskler"
    assert hazard["detail_category"] == "Merdivenler"
    assert hazard["recommended_ppe"] == []


def test_clean_area_does_not_create_a_risk(monkeypatch):
    from app.core.config import settings
    from app.services import ai_vision

    monkeypatch.setattr(settings, "vision_provider", "api")
    monkeypatch.setattr(settings, "vision_api_key", "test-key")
    monkeypatch.setattr(
        ai_vision,
        "_api_analyze",
        lambda **_kwargs: {"hazards": []},
    )

    result = ai_vision.analyze_media(image_bytes=b"clean-area")

    assert result["provider"] == "api"
    assert result["hazards"] == []
    assert result["bbox_annotations"] == []
    assert "uygunsuzluk bulunamadı" in result["note"]


def test_api_failure_is_fail_closed(monkeypatch):
    from app.core.config import settings
    from app.services import ai_vision

    monkeypatch.setattr(settings, "vision_provider", "api")
    monkeypatch.setattr(settings, "vision_api_key", "test-key")
    monkeypatch.setattr(ai_vision, "_api_analyze", lambda **_kwargs: None)

    result = ai_vision.analyze_media(
        image_bytes=b"api-error",
        media_text="Merdivende malzeme var",
        risk_activity="Genel saha",
        risk_definition="Fiziksel risk",
    )

    assert result["provider"] == "unavailable"
    assert result["hazards"] == []
    assert result["bbox_annotations"] == []
    assert "sahte görsel bulgu" in result["note"]


def test_visual_report_contains_only_relevant_controls():
    from app.services.ai_mevzuat import build_visual_report

    report = build_visual_report(
        hazard_key="stair_obstruction",
        text="Merdiven üzerinde kova ve poşet görülüyor.",
        confidence=0.95,
    )

    assert report is not None
    content = " ".join(
        [
            report["report_text"],
            *report["tedbirler"],
            *report["onleyici_faaliyet"],
        ]
    ).casefold()
    assert "merdiven" in content
    assert "geçiş" in content
    assert "depolama" in content
    for unrelated in ("gürültü", "titreşim", "radyasyon", "odyometri", "dozimetre"):
        assert unrelated not in content
    assert report["ceza_riski"]["status"] == "needs_expert_review"


def test_full_analysis_keeps_automatic_mevzuat_dof_and_term(monkeypatch):
    from app.services import ai_vision

    monkeypatch.setattr(
        ai_vision,
        "analyze_media",
        lambda **_kwargs: {
            "provider": "api",
            "hazards": [
                {
                    "category": "Fiziksel Riskler",
                    "severity": 4,
                    "confidence": 0.95,
                    "bbox": [0.55, 0.2, 0.3, 0.55],
                    "observed": "Merdiven basamakları üzerinde kova ve poşet bırakılmış.",
                    "note": "Geçişi daraltan takılma ve düşme tehlikesi.",
                }
            ],
            "bbox_annotations": [],
            "note": "Görüntü, vision API ile analiz edildi.",
        },
    )

    result = ai_vision.build_full_analysis(
        image_bytes=b"stair-photo",
        reference_date=date(2026, 9, 1),
    )

    assert result["provider"] == "api"
    assert len(result["hazards"]) == 1
    hazard = result["hazards"][0]
    assert hazard["hazard_key"] == "stair_obstruction"
    assert hazard["mevzuat"]["source"] == "ai_vision_visual_hazard"
    assert hazard["termin"]["term_days"] is not None
    assert hazard["dof_suggestions"]
    dof_text = " ".join(item["description"] for item in hazard["dof_suggestions"]).casefold()
    assert "merdiven" in dof_text
    assert "geçiş" in dof_text
    for unrelated in ("gürültü", "titreşim", "radyasyon", "odyometri", "dozimetre"):
        assert unrelated not in dof_text
