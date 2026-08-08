from __future__ import annotations

from app.services.training_presentation_phase9 import INSTRUCTOR_UI_VERSION
from app.services.training_presentation_phase9_scope_guard import finalize_phase9_manifest_scope


CONSTRUCTION_TOPICS = [
    "Yüksekte çalışma, düşmeyi önleme ve kurtarma - 30 DK",
    "İskele, merdiven, platform ve kenar koruma güvenliği - 30 DK",
    "Kazı, iksa, göçük ve yeraltı hatları - 30 DK",
    "Vinç, kaldırma ekipmanı ve düşen cisim riskleri - 30 DK",
    "Şantiye içi trafik, iş makineleri ve geçici elektrik - 30 DK",
]

PHASE8_ONLY_TOPICS = [
    "Kurşun tozu ve dumanı maruziyeti, mühendislik kontrolleri, hijyen ve sağlık gözetimi - 30 DK",
    "Sülfürik asitle güvenli çalışma, sıçrama, dökülme, acil duş ve göz duşu - 30 DK",
    "Akü şarjında hidrojen gazı, havalandırma, patlama ve ateşleme kaynakları - 30 DK",
    "Elektrik, kısa devre, makine güvenliği ve bakımda enerji izolasyonu - 30 DK",
    "Elle taşıma, yangın, acil durum, tahliye ve periyodik kontroller - 30 DK",
]


def _manifest(topics):
    return {
        "training_topics": list(topics),
        "rendering": {
            "traceability_ready": True,
            "instructor_mode_supported": True,
            "instructor_mode_ui": INSTRUCTOR_UI_VERSION,
            "coverage_v2_active": True,
        },
        "coverage_v2": {"phase9_full_profile": True},
        "slides": [
            {
                "position": index + 1,
                "section_id": "work_specific_topics",
                "title": topic,
                "source_refs": ["legacy-source"],
                "content_blocks": [],
            }
            for index, topic in enumerate(topics)
        ],
        "content_hash": "a" * 64,
    }


def test_full_phase9_profile_keeps_v2_and_freezes_official_slide_sources():
    original = _manifest(CONSTRUCTION_TOPICS)
    result = finalize_phase9_manifest_scope(original)

    assert result["rendering"]["instructor_mode_ui"] == INSTRUCTOR_UI_VERSION
    assert result["rendering"]["coverage_v2_active"] is True
    assert result["coverage_v2"]["phase9_full_profile"] is True
    assert result["coverage_v2"]["phase9_supported_count"] == 5
    assert all(slide["coverage_v2_source_controlled"] is True for slide in result["slides"])
    assert all("legacy-source" not in slide["source_refs"] for slide in result["slides"])
    assert all(any(ref.startswith("https://") for ref in slide["source_refs"]) for slide in result["slides"])
    assert result["content_hash"] != original["content_hash"]
    assert original["slides"][0]["source_refs"] == ["legacy-source"]


def test_phase8_only_profile_stays_v1_even_while_phase9_global_flag_is_on():
    original = _manifest(PHASE8_ONLY_TOPICS)
    result = finalize_phase9_manifest_scope(original)

    assert "coverage_v2" not in result
    assert "instructor_mode_ui" not in result["rendering"]
    assert "coverage_v2_active" not in result["rendering"]
    assert all(slide["source_refs"] == ["legacy-source"] for slide in result["slides"])
    assert len(result["content_hash"]) == 64
