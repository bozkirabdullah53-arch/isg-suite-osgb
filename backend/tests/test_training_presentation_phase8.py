from __future__ import annotations

import json

import pytest

from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_presentation_phase8 import (
    MANIFEST_VERSION,
    TRACEABILITY_VERSION,
    enrich_manifest_with_traceability,
    phase8_exact_questions,
    traceability_readiness,
    validate_manifest_traceability,
)


def _snapshot(topics=None) -> TrainingNaceSnapshot:
    values = topics or [
        "Kurşun tozu ve dumanı maruziyeti, mühendislik kontrolleri, hijyen ve sağlık gözetimi - 30 DK",
        "Sülfürik asitle güvenli çalışma, sıçrama, dökülme, acil duş ve göz duşu - 30 DK",
        "Akü şarjında hidrojen gazı, havalandırma, patlama ve ateşleme kaynakları - 30 DK",
        "Elektrik, kısa devre, makine güvenliği ve bakımda enerji izolasyonu - 30 DK",
        "Elle taşıma, yangın, acil durum, tahliye ve periyodik kontroller - 30 DK",
    ]
    return TrainingNaceSnapshot(
        id=1,
        training_id=1,
        company_id=118,
        branch_id=None,
        catalog_key="nace_27_20_01",
        nace_code="27.20.01",
        nace_description="Elektrik akümülatör parçalarının imalatı",
        nace_section_code="C",
        nace_section_name="İmalat",
        subsector_code="27",
        activity_group_code="27.20",
        content_profile_code="aku_uretimi",
        content_profile_name="Akü üretimi",
        hazard_class="Çok Tehlikeli",
        training_topics_json=json.dumps(values, ensure_ascii=False),
        technical_risk_tags_json=json.dumps(["lead_exposure", "sulfuric_acid", "hydrogen_gas", "chemical_spill", "health_surveillance"]),
        special_risks_json=json.dumps(["lead_poisoning", "acid_burn", "hydrogen_explosion"]),
        required_duration_minutes=720,
        required_duration_hours=16,
        classification_status="verified",
        catalog_version="test-v1",
        catalog_hash="a" * 64,
        source_snapshot_json="{}",
    )


def _base_manifest(snapshot: TrainingNaceSnapshot) -> dict:
    slides = [
        {"position": 1, "section_id": "cover", "title": "Kapak", "source_refs": ["snapshot"], "content_blocks": []},
        {"position": 2, "section_id": "learning_objectives", "title": "Amaç", "source_refs": ["csgb-training-guide"], "content_blocks": []},
        {"position": 3, "section_id": "legal_basis", "title": "Mevzuat", "source_refs": ["tr-law-6331"], "content_blocks": []},
        {"position": 4, "section_id": "nace_identity", "title": "NACE", "source_refs": ["snapshot"], "content_blocks": []},
        {"position": 5, "section_id": "training_plan", "title": "Plan", "source_refs": ["snapshot"], "content_blocks": []},
        {"position": 6, "section_id": "foundation_ohs", "title": "Temel 1", "source_refs": ["tr-law-6331"], "content_blocks": []},
        {"position": 7, "section_id": "foundation_ohs", "title": "Temel 2", "source_refs": ["tr-law-6331"], "content_blocks": []},
    ]
    for index, topic in enumerate(json.loads(snapshot.training_topics_json), start=8):
        slides.append({
            "position": index,
            "section_id": "work_specific_topics",
            "title": topic,
            "source_refs": ["csgb-training-guide"],
            "content_blocks": [
                {"type": "frozen_training_topic", "value": topic},
                {"type": "technical_content_pending_renderer", "value": True},
            ],
        })
    for section, title in [
        ("technical_risks", "Riskler"),
        ("control_measures", "Kontroller"),
        ("ppe", "KKD"),
        ("emergency", "Acil durum"),
        ("assessment", "Değerlendirme"),
        ("summary", "Özet"),
        ("sources_and_version", "Kaynaklar"),
    ]:
        slides.append({"position": len(slides) + 1, "section_id": section, "title": title, "source_refs": ["tr-law-6331"], "content_blocks": []})
    return {
        "manifest_version": "nace-training-presentation-manifest-v1",
        "contract_version": "nace-training-presentation-contract-v1",
        "contract_hash": "b" * 64,
        "template_version": "osgb-training-presentation-template-v1",
        "output_formats": ["pptx", "pdf"],
        "training": {"training_id": 1, "company_id": 118, "title": "Test"},
        "nace_snapshot": {"nace_code": snapshot.nace_code, "nace_description": snapshot.nace_description},
        "training_topics": json.loads(snapshot.training_topics_json),
        "technical_risk_tags": json.loads(snapshot.technical_risk_tags_json),
        "special_risks": json.loads(snapshot.special_risks_json),
        "exam_readiness": {"policy": "exact-nace", "foundation": 5, "work_specific": 15, "ready": True},
        "source_registry": [],
        "slides": slides,
        "slide_count": len(slides),
        "approval": {"status": "specialist_review_required", "required_slide_positions": []},
        "rendering": {"supported": False, "storage_write": False},
        "core_training_unaffected": True,
        "content_hash": "c" * 64,
    }


def test_phase8_generates_fifteen_distinct_risk_aligned_questions():
    questions = phase8_exact_questions(_snapshot())
    assert len(questions) == 15
    assert len({item["question_code"] for item in questions}) == 15
    assert {item["version"] for item in questions} == {2}
    assert all(len(item["options"]) == 4 for item in questions)
    assert all(item["sources"] for item in questions)
    assert "Kurşun" in questions[0]["options"][0]
    assert "hidrojen" in " ".join(item["question_text"] for item in questions).casefold()


def test_phase8_manifest_requires_and_proves_twenty_of_twenty_coverage():
    snapshot = _snapshot()
    enriched = enrich_manifest_with_traceability(_base_manifest(snapshot), snapshot)
    assert enriched["manifest_version"] == MANIFEST_VERSION
    trace = enriched["traceability"]
    assert trace["version"] == TRACEABILITY_VERSION
    assert trace["coverage"] == {
        "question_total": 20,
        "linked_questions": 20,
        "source_linked_questions": 20,
        "orphan_questions": 0,
        "cross_sector_fallback": False,
        "supported_topics": 5,
        "status": "passed",
    }
    assert len(trace["learning_concepts"]) == 20
    assert len(trace["question_links"]) == 20
    assert validate_manifest_traceability(enriched)["ok"] is True
    work_slides = [slide for slide in enriched["slides"] if slide["section_id"] == "work_specific_topics"]
    assert len(work_slides) == 5
    assert all(not any(block.get("type") == "technical_content_pending_renderer" for block in slide["content_blocks"]) for slide in work_slides)
    assert all(any(block.get("type") == "tehlike" for block in slide["content_blocks"]) for slide in work_slides)


def test_phase8_fails_closed_for_unreviewed_topic():
    topics = ["Desteklenmeyen özgün proses konusu"] * 5
    readiness = traceability_readiness(topics)
    assert readiness["ready"] is False
    with pytest.raises(ValueError, match="güvenilir teknik bilgi paketi"):
        phase8_exact_questions(_snapshot(topics))


def test_traceability_validator_rejects_orphan_question():
    snapshot = _snapshot()
    manifest = enrich_manifest_with_traceability(_base_manifest(snapshot), snapshot)
    manifest["traceability"]["question_links"][0]["slide_positions"] = [999]
    with pytest.raises(ValueError, match="orphan_slide"):
        validate_manifest_traceability(manifest)
