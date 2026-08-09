from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.training_presentation_contract import (
    CONTRACT_VERSION,
    TEMPLATE_VERSION,
    PresentationContractError,
    build_presentation_manifest_preview,
    load_presentation_contract,
    presentation_contract_payload,
)


IT_TOPICS = [
    "Ekranlı araçlarla çalışma, göz sağlığı ve mola düzeni",
    "Oturma düzeni, ergonomi ve tekrarlayan zorlanmalar",
    "Sistem odası: elektrik, sıcaklık ve yangın riskleri",
    "Kablo düzeni, kayma-takılma ve düzenli çalışma alanı",
    "Uzun çalışma saatleri, iş yükü ve psikososyal riskler",
]


def _training():
    return SimpleNamespace(
        id=101,
        company_id=35,
        branch_id=None,
        title="Temel İş Sağlığı ve Güvenliği Eğitimi",
        start_date=date(2026, 8, 6),
        end_date=date(2026, 8, 7),
    )


def _snapshot(*, status: str = "verified", topics: list[str] | None = None):
    return SimpleNamespace(
        training_id=101,
        catalog_key="nace_62_01_01",
        nace_code="62.01.01",
        nace_description="Bilgisayar programlama faaliyetleri",
        hazard_class="Az Tehlikeli",
        content_profile_code="bilisim_yazilim_it",
        classification_status=status,
        catalog_version="nace-test-v1",
        catalog_hash="a" * 64,
        training_topics_json=json.dumps(topics if topics is not None else IT_TOPICS, ensure_ascii=False),
        technical_risk_tags_json=json.dumps(
            ["display_screen", "server_room", "psychosocial"], ensure_ascii=False
        ),
        special_risks_json=json.dumps(["uzun_sureli_ekran"], ensure_ascii=False),
        required_duration_hours=8,
        required_duration_minutes=360,
    )


def _exam(*, foundation: int = 5, work_specific: int = 15, ready: bool = True):
    return {
        "ready": ready,
        "available": {"foundation": foundation, "work_specific": work_specific},
        "policy": "exact-nace-test",
    }


def test_contract_is_versioned_approved_and_machine_validated():
    contract = load_presentation_contract()
    payload = presentation_contract_payload()

    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["status"] == "approved_for_implementation"
    assert contract["outputs"] == {
        "primary": "pptx",
        "companions": ["pdf"],
        "pdf_strategy": "native-renderer-from-same-manifest",
        "office_conversion_allowed": False,
        "reason": contract["outputs"]["reason"],
    }
    assert payload["template_version"] == TEMPLATE_VERSION
    assert len(payload["contract_hash"]) == 64
    assert payload["renderer_available"] is False
    assert payload["generation_supported"] is False
    assert payload["core_training_unaffected"] is True


def test_contract_contains_all_required_sections_in_stable_order():
    contract = load_presentation_contract()
    section_ids = [item["section_id"] for item in contract["sections"]]
    assert section_ids == [
        "cover",
        "learning_objectives",
        "legal_basis",
        "nace_identity",
        "training_plan",
        "foundation_ohs",
        "work_specific_topics",
        "technical_risks",
        "control_measures",
        "ppe",
        "emergency",
        "assessment",
        "summary",
        "sources_and_version",
    ]
    assert all(item["required"] is True for item in contract["sections"])
    assert contract["layout"]["minimum_slide_count"] == 18
    assert contract["layout"]["maximum_slide_count"] == 32


def test_contract_uses_current_2026_training_regulation_and_official_sources():
    contract = load_presentation_contract()
    registry = {item["source_id"]: item for item in contract["source_registry"]}
    regulation = registry["tr-training-regulation-2026"]
    assert regulation["url"] == "https://www.resmigazete.gov.tr/eskiler/2026/04/20260402-2.htm"
    assert "33212" in regulation["reference"]
    assert regulation["checked_at"] == "2026-08-06"
    assert registry["csgb-training-faq-2026"]["publisher"].startswith("T.C.")


def test_contract_forbids_invention_and_cross_sector_fallback():
    policy = load_presentation_contract()["source_policy"]
    forbidden = set(policy["forbidden_source_types"])
    assert "cross_sector_fallback" in forbidden
    assert "legacy_sector_guess" in forbidden
    assert "model_only_assertion" in forbidden
    assert "unsourced_technical_claim" in forbidden
    assert "Eksik veri uydurulmaz" in policy["no_invention_rule"]


def test_verified_it_snapshot_builds_deterministic_21_slide_preview():
    first = build_presentation_manifest_preview(
        training=_training(), snapshot=_snapshot(), exam_readiness=_exam()
    )
    second = build_presentation_manifest_preview(
        training=_training(), snapshot=_snapshot(), exam_readiness=_exam()
    )

    assert first == second
    assert first["manifest_version"] == "nace-training-presentation-manifest-v1"
    assert first["contract_version"] == CONTRACT_VERSION
    assert first["template_version"] == TEMPLATE_VERSION
    assert first["output_formats"] == ["pptx", "pdf"]
    assert first["slide_count"] == 21
    assert len(first["content_hash"]) == 64
    assert first["rendering"] == {
        "supported": False,
        "storage_write": False,
        "reason": "Phase 2 yalnız içerik manifesti ve sözleşme doğrulamasıdır.",
    }
    assert first["core_training_unaffected"] is True
    assert first["training_topics"] == IT_TOPICS
    assert first["nace_snapshot"]["nace_code"] == "62.01.01"
    assert first["nace_snapshot"]["content_profile_code"] == "bilisim_yazilim_it"
    cover = next(slide for slide in first["slides"] if slide["section_id"] == "cover")
    training_date = next(block for block in cover["content_blocks"] if block["type"] == "training_date")
    assert training_date == {
        "type": "training_date",
        "value": "06.08.2026 – 07.08.2026",
        "start_date": "06.08.2026",
        "end_date": "07.08.2026",
    }


def test_each_frozen_topic_has_its_own_work_specific_slide_without_unrelated_content():
    manifest = build_presentation_manifest_preview(
        training=_training(), snapshot=_snapshot(), exam_readiness=_exam()
    )
    topic_slides = [
        slide for slide in manifest["slides"]
        if slide["section_id"] == "work_specific_topics"
    ]
    assert [slide["title"] for slide in topic_slides] == IT_TOPICS
    serialized = json.dumps(manifest, ensure_ascii=False).casefold()
    for forbidden in ("forklift", "iskele", "kaynak dumanı", "gıda hijyeni"):
        assert forbidden not in serialized


def test_workplace_specific_fields_are_placeholders_requiring_specialist_approval():
    manifest = build_presentation_manifest_preview(
        training=_training(), snapshot=_snapshot(), exam_readiness=_exam()
    )
    assert manifest["approval"]["status"] == "specialist_review_required"
    assert manifest["approval"]["required_slide_positions"]
    emergency = next(
        slide for slide in manifest["slides"] if slide["section_id"] == "emergency"
    )
    assert emergency["approval_required"] is True
    assert all(block["value"] is None for block in emergency["content_blocks"])


@pytest.mark.parametrize(
    ("snapshot", "exam", "expected"),
    [
        (None, _exam(), "Persisted NACE snapshot bulunmuyor"),
        (_snapshot(status="legacy_unverified"), _exam(), "NACE snapshot doğrulanmış değil"),
        (_snapshot(topics=IT_TOPICS[:4]), _exam(), "tam olarak 5 eğitim konusu"),
        (_snapshot(), _exam(work_specific=14), "5 + 15 NACE sınav içeriği hazır değil"),
    ],
)
def test_manifest_fails_closed_without_touching_core_workflow(snapshot, exam, expected):
    with pytest.raises(PresentationContractError) as exc:
        build_presentation_manifest_preview(
            training=_training(), snapshot=snapshot, exam_readiness=exam
        )
    assert expected in str(exc.value)
