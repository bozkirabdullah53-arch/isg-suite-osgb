from __future__ import annotations

import json

from app.models.training_nace import TrainingNaceSnapshot
from app.services import training_presentation_phase8 as phase8
from app.services.training_presentation_phase10_chemicals import (
    CHEMICAL_PACK_ENV,
    CHEMICAL_PACK_FORCE_OFF_ENV,
    CHEMICAL_PACK_VERSION,
    chemical_coverage_readiness,
    chemical_pack_active,
    install_training_presentation_phase10_chemicals,
    resolve_chemical_topic_knowledge,
)


CHEMICAL_TOPICS = [
    "Kimyasal etiketler, SDS ve maruziyet yolları - 30 DK",
    "Solvent, izosiyanat, aerosol ve toksik buhar maruziyeti - 30 DK",
    "Yanıcı atmosfer, statik elektrik ve ex-proof ekipman - 30 DK",
    "Uyumsuz kimyasalların güvenli depolanması ve transferi - 30 DK",
    "Dökülme, sızıntı, acil duş ve müdahale prosedürleri - 30 DK",
]


def _snapshot() -> TrainingNaceSnapshot:
    return TrainingNaceSnapshot(
        id=1,
        training_id=90,
        company_id=118,
        branch_id=None,
        catalog_key="nace_20_30_90",
        nace_code="20.30.90",
        nace_description="Diğer boya, vernik ve ilgili ürünlerin imalatı",
        nace_section_code="C",
        nace_section_name="İmalat",
        subsector_code="20",
        activity_group_code="20.30",
        content_profile_code="kimyasal_boya",
        content_profile_name="Kimya, Boya ve Kaplama",
        hazard_class="Çok Tehlikeli",
        training_topics_json=json.dumps(CHEMICAL_TOPICS, ensure_ascii=False),
        technical_risk_tags_json=json.dumps(["solvents", "isocyanates", "toxic_vapour", "atex", "chemical_storage"]),
        special_risks_json="[]",
        required_duration_minutes=720,
        required_duration_hours=16,
        classification_status="verified",
        catalog_version="phase10-chemical-test",
        catalog_hash="a" * 64,
        source_snapshot_json="{}",
    )


def _manifest() -> dict:
    return {
        "training_topics": list(CHEMICAL_TOPICS),
        "nace_snapshot": {"nace_code": "20.30.90", "nace_description": "Diğer boya, vernik ve ilgili ürünlerin imalatı"},
        "slides": [
            {"position": 1, "section_id": "foundation_ohs", "title": "Temel İSG 1", "source_refs": ["https://www.csgb.gov.tr/"]},
            {"position": 2, "section_id": "foundation_ohs", "title": "Temel İSG 2", "source_refs": ["https://www.csgb.gov.tr/"]},
            *[
                {
                    "position": index + 3,
                    "section_id": "work_specific_topics",
                    "title": topic,
                    "content_blocks": [{"type": "technical_content_pending_renderer", "value": "bekliyor"}],
                    "source_refs": [],
                }
                for index, topic in enumerate(CHEMICAL_TOPICS)
            ],
        ],
        "rendering": {},
        "content_hash": "b" * 64,
    }


def test_chemical_pack_flag_is_fail_closed(monkeypatch):
    monkeypatch.delenv(CHEMICAL_PACK_ENV, raising=False)
    monkeypatch.delenv(CHEMICAL_PACK_FORCE_OFF_ENV, raising=False)
    assert chemical_pack_active() is False

    monkeypatch.setenv(CHEMICAL_PACK_ENV, "true")
    assert chemical_pack_active() is True

    monkeypatch.setenv(CHEMICAL_PACK_FORCE_OFF_ENV, "true")
    assert chemical_pack_active() is False


def test_chemical_pack_has_exact_five_reviewed_topics():
    resolved = [resolve_chemical_topic_knowledge(topic) for topic in CHEMICAL_TOPICS]
    assert len(resolved) == 5
    assert all(item is not None for item in resolved)
    assert len({item["code"] for item in resolved if item}) == 5
    assert all(len(item["controls"]) == 2 for item in resolved if item)
    assert all(len(item["sources"]) >= 2 for item in resolved if item)
    assert all(item["coverage_version"] == CHEMICAL_PACK_VERSION for item in resolved if item)


def test_chemical_pack_does_not_match_generic_words():
    assert resolve_chemical_topic_knowledge("Yangın, elektrik ve kimyasal riskler") is None
    assert resolve_chemical_topic_knowledge("Solvent kullanımı") is None
    assert resolve_chemical_topic_knowledge("Depolama ve transfer") is None


def test_chemical_pack_unlocks_exact_nace_203090_exam(monkeypatch):
    install_training_presentation_phase10_chemicals()
    monkeypatch.setenv(CHEMICAL_PACK_ENV, "true")
    monkeypatch.delenv(CHEMICAL_PACK_FORCE_OFF_ENV, raising=False)

    readiness = chemical_coverage_readiness(CHEMICAL_TOPICS)
    assert readiness["full_profile"] is True
    assert readiness["supported_count"] == 5

    traceability = phase8.traceability_readiness(CHEMICAL_TOPICS)
    assert traceability["ready"] is True
    assert traceability["supported_count"] == 5
    assert traceability["missing_topics"] == []

    questions = phase8.phase8_exact_questions(_snapshot())
    assert len(questions) == 15
    assert len({item["question_code"] for item in questions}) == 15
    assert all(item["question_code"].startswith("TR-NACE-203090-") for item in questions)
    assert all(item["sources"] for item in questions)
    assert all(item["knowledge_pack_code"].startswith("chemical-") for item in questions)


def test_chemical_pack_unlocks_twenty_of_twenty_presentation_traceability(monkeypatch):
    install_training_presentation_phase10_chemicals()
    monkeypatch.setenv(CHEMICAL_PACK_ENV, "true")
    monkeypatch.delenv(CHEMICAL_PACK_FORCE_OFF_ENV, raising=False)

    enriched = phase8.enrich_manifest_with_traceability(_manifest(), _snapshot())
    result = phase8.validate_manifest_traceability(enriched)

    assert result["ok"] is True
    assert result["question_total"] == 20
    assert result["linked_questions"] == 20
    assert result["source_linked_questions"] == 20
    assert enriched["traceability"]["coverage"]["cross_sector_fallback"] is False
    work_slides = [slide for slide in enriched["slides"] if slide["section_id"] == "work_specific_topics"]
    assert len(work_slides) == 5
    assert all(slide.get("knowledge_pack_code", "").startswith("chemical-") for slide in work_slides)
    assert all(not any(block.get("type") == "technical_content_pending_renderer" for block in slide.get("content_blocks", [])) for slide in work_slides)


def test_chemical_pack_force_off_preserves_existing_fail_closed_behavior(monkeypatch):
    install_training_presentation_phase10_chemicals()
    monkeypatch.setenv(CHEMICAL_PACK_ENV, "true")
    monkeypatch.setenv(CHEMICAL_PACK_FORCE_OFF_ENV, "true")

    readiness = phase8.traceability_readiness(CHEMICAL_TOPICS)
    assert readiness["ready"] is False
    assert readiness["supported_count"] < 5
