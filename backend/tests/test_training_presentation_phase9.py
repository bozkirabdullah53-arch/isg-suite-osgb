from __future__ import annotations

import json

from app.models.training_nace import TrainingNaceSnapshot
from app.services import training_presentation_phase8 as phase8
from app.services.training_presentation_phase9 import (
    COVERAGE_V2_ENV,
    COVERAGE_V2_FORCE_OFF_ENV,
    COVERAGE_V2_VERSION,
    INSTRUCTOR_UI_VERSION,
    install_training_presentation_phase9,
    mark_manifest_for_phase9_ui,
    phase9_active,
    phase9_coverage_readiness,
    resolve_phase9_topic_knowledge,
)


CONSTRUCTION_TOPICS = [
    "Yüksekte çalışma, düşmeyi önleme ve kurtarma - 30 DK",
    "İskele, merdiven, platform ve kenar koruma güvenliği - 30 DK",
    "Kazı, iksa, göçük ve yeraltı hatları - 30 DK",
    "Vinç, kaldırma ekipmanı ve düşen cisim riskleri - 30 DK",
    "Şantiye içi trafik, iş makineleri ve geçici elektrik - 30 DK",
]

LOGISTICS_TOPICS = [
    "Forklift, transpalet ve yaya trafiği güvenliği - 30 DK",
    "Raf sistemleri, istif ve yük düşmesi riskleri - 30 DK",
    "Yükleme rampası, dorse ve araç sabitleme - 30 DK",
    "Elle taşıma, kaldırma yardımcıları ve ergonomi - 30 DK",
    "Akü şarj alanı, yangın ve acil çıkış düzeni - 30 DK",
]

HEALTH_TOPICS = [
    "Biyolojik etkenler, enfeksiyon kontrolü ve izolasyon - 30 DK",
    "Kesici-delici yaralanmaları ve tıbbi atıklar - 30 DK",
    "Hasta taşıma, ergonomi ve şiddet riski - 30 DK",
    "İlaç, dezenfektan, sterilizasyon ve radyasyon riskleri - 30 DK",
    "Acil durum, tahliye ve güvenli sağlık hizmeti sunumu - 30 DK",
]


def _snapshot(*, nace_code: str, profile: str, topics: list[str]) -> TrainingNaceSnapshot:
    return TrainingNaceSnapshot(
        id=1,
        training_id=1,
        company_id=118,
        branch_id=None,
        catalog_key=f"nace_{nace_code.replace('.', '_')}",
        nace_code=nace_code,
        nace_description=f"{profile} test faaliyeti",
        nace_section_code="X",
        nace_section_name="Test",
        subsector_code=nace_code.split(".")[0],
        activity_group_code=".".join(nace_code.split(".")[:2]),
        content_profile_code=profile,
        content_profile_name=profile,
        hazard_class="Çok Tehlikeli",
        training_topics_json=json.dumps(topics, ensure_ascii=False),
        technical_risk_tags_json="[]",
        special_risks_json="[]",
        required_duration_minutes=720,
        required_duration_hours=16,
        classification_status="verified",
        catalog_version="phase9-test",
        catalog_hash="a" * 64,
        source_snapshot_json="{}",
    )


def test_phase9_flag_is_fail_closed(monkeypatch):
    monkeypatch.delenv(COVERAGE_V2_ENV, raising=False)
    monkeypatch.delenv(COVERAGE_V2_FORCE_OFF_ENV, raising=False)
    assert phase9_active() is False

    monkeypatch.setenv(COVERAGE_V2_ENV, "true")
    assert phase9_active() is True

    monkeypatch.setenv(COVERAGE_V2_FORCE_OFF_ENV, "true")
    assert phase9_active() is False


def test_phase9_has_fifteen_exact_curated_topic_packs():
    topics = CONSTRUCTION_TOPICS + LOGISTICS_TOPICS + HEALTH_TOPICS
    resolved = [resolve_phase9_topic_knowledge(topic) for topic in topics]
    assert len(resolved) == 15
    assert all(item is not None for item in resolved)
    assert len({item["code"] for item in resolved if item}) == 15
    assert all(len(item["controls"]) == 2 for item in resolved if item)
    assert all(len(item["sources"]) >= 2 for item in resolved if item)
    assert all(item["coverage_version"] == COVERAGE_V2_VERSION for item in resolved if item)


def test_phase9_avoids_ambiguous_generic_topic_matches():
    assert resolve_phase9_topic_knowledge("Elektrik, trafik, yangın ve ergonomi") is None
    assert resolve_phase9_topic_knowledge("Genel üretim riskleri ve KKD") is None


def test_phase9_exact_first_resolver_overrides_generic_phase8_match(monkeypatch):
    install_training_presentation_phase9()
    monkeypatch.setenv(COVERAGE_V2_ENV, "true")
    monkeypatch.delenv(COVERAGE_V2_FORCE_OFF_ENV, raising=False)

    item = phase8.resolve_topic_knowledge(CONSTRUCTION_TOPICS[-1])
    assert item is not None
    assert item["code"] == "construction-traffic-temporary-electric"


def test_phase9_disabled_delegates_to_phase8(monkeypatch):
    install_training_presentation_phase9()
    monkeypatch.setenv(COVERAGE_V2_ENV, "false")
    monkeypatch.delenv(COVERAGE_V2_FORCE_OFF_ENV, raising=False)

    item = phase8.resolve_topic_knowledge(CONSTRUCTION_TOPICS[-1])
    assert item is not None
    assert item["code"] != "construction-traffic-temporary-electric"


def test_each_phase9_profile_unlocks_phase8_twenty_of_twenty_question_contract(monkeypatch):
    install_training_presentation_phase9()
    monkeypatch.setenv(COVERAGE_V2_ENV, "true")
    monkeypatch.delenv(COVERAGE_V2_FORCE_OFF_ENV, raising=False)

    profiles = [
        ("41.20.01", "insaat", CONSTRUCTION_TOPICS),
        ("52.10.01", "depo_lojistik", LOGISTICS_TOPICS),
        ("86.10.01", "saglik", HEALTH_TOPICS),
    ]
    for nace_code, profile, topics in profiles:
        readiness = phase8.traceability_readiness(topics)
        assert readiness["ready"] is True
        assert readiness["supported_count"] == 5

        questions = phase8.phase8_exact_questions(_snapshot(nace_code=nace_code, profile=profile, topics=topics))
        assert len(questions) == 15
        assert len({item["question_code"] for item in questions}) == 15
        assert all(item["sources"] for item in questions)
        assert all(item["knowledge_pack_code"] for item in questions)

        phase9_readiness = phase9_coverage_readiness(topics)
        assert phase9_readiness["phase9_full_profile"] is True
        assert phase9_readiness["phase9_supported_count"] == 5


def test_phase9_manifest_marker_is_additive_and_rehashes(monkeypatch):
    monkeypatch.setenv(COVERAGE_V2_ENV, "true")
    monkeypatch.delenv(COVERAGE_V2_FORCE_OFF_ENV, raising=False)
    original = {
        "training_topics": CONSTRUCTION_TOPICS,
        "rendering": {"traceability_ready": True, "instructor_mode_supported": True},
        "content_hash": "b" * 64,
    }
    marked = mark_manifest_for_phase9_ui(original)

    assert original["content_hash"] == "b" * 64
    assert "instructor_mode_ui" not in original["rendering"]
    assert marked["rendering"]["instructor_mode_ui"] == INSTRUCTOR_UI_VERSION
    assert marked["rendering"]["coverage_v2_active"] is True
    assert marked["coverage_v2"]["phase9_full_profile"] is True
    assert marked["coverage_v2"]["phase9_supported_count"] == 5
    assert marked["content_hash"] != original["content_hash"]
    assert len(marked["content_hash"]) == 64
