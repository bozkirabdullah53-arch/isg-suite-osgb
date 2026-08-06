"""Versioned content contract and deterministic preview manifest for NACE presentations.

This module does not render, persist or upload a presentation. It validates the
source-controlled Phase 2 contract and can build a read-only manifest preview
from an existing verified NACE snapshot. Missing data fails closed and never
blocks the core training, exam, PDF or certificate workflows.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models.entities import TrainingSession
from app.models.training_nace import TrainingNaceSnapshot

CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "training_presentation_contract_v1.json"
)
CONTRACT_VERSION = "nace-training-presentation-contract-v1"
TEMPLATE_VERSION = "osgb-training-presentation-template-v1"


class PresentationContractError(ValueError):
    """Contract or manifest source data is incomplete or unsafe."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _json_list(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("contract_version") != CONTRACT_VERSION:
        raise PresentationContractError("Sunum içerik sözleşmesi sürümü geçersiz.")
    if contract.get("status") != "approved_for_implementation":
        raise PresentationContractError("Sunum içerik sözleşmesi onaylı değil.")

    outputs = contract.get("outputs") or {}
    if outputs.get("primary") != "pptx" or "pdf" not in (outputs.get("companions") or []):
        raise PresentationContractError("Çıktı sözleşmesi PPTX ana + PDF yardımcı olmalıdır.")
    if outputs.get("office_conversion_allowed") is not False:
        raise PresentationContractError("Office dönüşümü güvenli sözleşmede kapalı olmalıdır.")

    layout = contract.get("layout") or {}
    minimum = int(layout.get("minimum_slide_count") or 0)
    target = int(layout.get("target_slide_count") or 0)
    maximum = int(layout.get("maximum_slide_count") or 0)
    if not (18 <= minimum <= target <= maximum <= 32):
        raise PresentationContractError("Sunum slayt aralığı 18–32 içinde tutarlı değil.")

    allowed = set((contract.get("source_policy") or {}).get("allowed_source_types") or [])
    forbidden = set((contract.get("source_policy") or {}).get("forbidden_source_types") or [])
    if not allowed or not forbidden or allowed & forbidden:
        raise PresentationContractError("Kaynak izin ve yasak listeleri geçersiz.")
    required_source_types = {
        "frozen_nace_snapshot",
        "controlled_training_topics",
        "controlled_risk_catalog",
        "official_legislation",
        "official_csgb_guidance",
    }
    if not required_source_types <= allowed:
        raise PresentationContractError("Zorunlu sunum kaynak tipleri eksik.")

    registry = contract.get("source_registry") or []
    source_ids = [str(item.get("source_id") or "") for item in registry]
    if len(source_ids) != len(set(source_ids)) or any(not item for item in source_ids):
        raise PresentationContractError("Resmî kaynak kimlikleri boş veya mükerrer.")
    for item in registry:
        if not str(item.get("url") or "").startswith("https://"):
            raise PresentationContractError("Kaynak adresi güvenli HTTPS olmalıdır.")
        if item.get("source_type") not in allowed:
            raise PresentationContractError("Kaynak kayıt tipi izin listesinde değil.")
        if not item.get("checked_at"):
            raise PresentationContractError("Kaynak kontrol tarihi zorunludur.")

    sections = contract.get("sections") or []
    required_sections = {
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
    }
    section_ids = [str(item.get("section_id") or "") for item in sections]
    if set(section_ids) != required_sections or len(section_ids) != len(set(section_ids)):
        raise PresentationContractError("Zorunlu sunum bölümleri eksik veya mükerrer.")
    orders = [int(item.get("order") or 0) for item in sections]
    if orders != sorted(orders) or len(orders) != len(set(orders)):
        raise PresentationContractError("Sunum bölüm sırası benzersiz ve artan olmalıdır.")
    for section in sections:
        if section.get("required") is not True:
            raise PresentationContractError("v1 sözleşmesindeki tüm bölümler zorunludur.")
        section_sources = set(section.get("sources") or [])
        if not section_sources or not section_sources <= allowed:
            raise PresentationContractError("Bölümde izin verilmeyen veya eksik kaynak tipi var.")
        if not section.get("content_rule") or not section.get("required_fields"):
            raise PresentationContractError("Bölüm içerik ve alan kuralı eksik.")

    fail_closed = contract.get("fail_closed") or {}
    if fail_closed.get("non_blocking_for_core_training") is not True:
        raise PresentationContractError("Sunum hatası çekirdek eğitimi etkilememelidir.")
    blockers = set(fail_closed.get("blocking_conditions") or [])
    for code in (
        "missing_verified_nace_snapshot",
        "training_topic_count_not_five",
        "cross_sector_fallback_detected",
        "unsourced_claim_detected",
    ):
        if code not in blockers:
            raise PresentationContractError(f"Fail-closed koşulu eksik: {code}")


@lru_cache(maxsize=1)
def load_presentation_contract() -> dict[str, Any]:
    try:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PresentationContractError("Sunum içerik sözleşmesi okunamadı.") from exc
    if not isinstance(contract, dict):
        raise PresentationContractError("Sunum içerik sözleşmesi nesne olmalıdır.")
    _validate_contract(contract)
    return contract


def presentation_contract_payload() -> dict[str, Any]:
    contract = load_presentation_contract()
    return {
        **contract,
        "template_version": TEMPLATE_VERSION,
        "contract_hash": _sha256(contract),
        "read_only": True,
        "renderer_available": False,
        "generation_supported": False,
        "core_training_unaffected": True,
    }


def _require_verified_snapshot(snapshot: TrainingNaceSnapshot | None) -> TrainingNaceSnapshot:
    if snapshot is None:
        raise PresentationContractError("Persisted NACE snapshot bulunmuyor.")
    if str(snapshot.classification_status or "") != "verified":
        raise PresentationContractError("NACE snapshot doğrulanmış değil.")
    if not str(snapshot.catalog_key or "").startswith("nace_"):
        raise PresentationContractError("Tam NACE katalog anahtarı bulunmuyor.")
    if not str(snapshot.nace_code or "").strip() or not str(snapshot.nace_description or "").strip():
        raise PresentationContractError("NACE kodu veya açıklaması eksik.")
    return snapshot


def _slide(
    *,
    position: int,
    section_id: str,
    title: str,
    source_refs: list[str],
    content_blocks: list[dict[str, Any]],
    approval_required: bool = False,
) -> dict[str, Any]:
    return {
        "position": position,
        "section_id": section_id,
        "title": title,
        "source_refs": source_refs,
        "content_blocks": content_blocks,
        "speaker_notes_required": True,
        "approval_required": approval_required,
    }


def build_presentation_manifest_preview(
    *,
    training: TrainingSession,
    snapshot: TrainingNaceSnapshot | None,
    exam_readiness: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build deterministic, non-rendering content manifest for specialist review."""
    snapshot = _require_verified_snapshot(snapshot)
    contract = load_presentation_contract()
    topics = _json_list(snapshot.training_topics_json)
    risks = _json_list(snapshot.technical_risk_tags_json)
    special_risks = _json_list(snapshot.special_risks_json)
    if len(topics) != 5:
        raise PresentationContractError(
            f"Sunum için tam olarak 5 eğitim konusu gerekir; bulunan: {len(topics)}."
        )
    if not risks:
        raise PresentationContractError("Sunum için teknik risk etiketi bulunmuyor.")
    exam = dict(exam_readiness or {})
    available = dict(exam.get("available") or {})
    foundation_count = int(available.get("foundation") or 0)
    work_specific_count = int(available.get("work_specific") or 0)
    if not exam.get("ready") or foundation_count != 5 or work_specific_count != 15:
        raise PresentationContractError("Mevcut 5 + 15 NACE sınav içeriği hazır değil.")

    official_source_ids = [
        str(item["source_id"])
        for item in contract["source_registry"]
    ]
    snapshot_ref = f"training_nace_snapshot:{snapshot.training_id}:{snapshot.catalog_hash}"
    topic_ref = f"controlled_training_topics:{snapshot.catalog_hash}"
    risk_ref = f"controlled_risk_catalog:{snapshot.content_profile_code}:{snapshot.catalog_hash}"
    exam_ref = f"approved_question_bank:{exam.get('policy') or 'exact-nace-5-plus-15'}"

    slides: list[dict[str, Any]] = []

    def add(
        section_id: str,
        title: str,
        source_refs: list[str],
        content_blocks: list[dict[str, Any]],
        *,
        approval_required: bool = False,
    ) -> None:
        slides.append(
            _slide(
                position=len(slides) + 1,
                section_id=section_id,
                title=title,
                source_refs=source_refs,
                content_blocks=content_blocks,
                approval_required=approval_required,
            )
        )

    add(
        "cover",
        str(getattr(training, "title", None) or "NACE Uyumlu İş Sağlığı ve Güvenliği Eğitimi"),
        [snapshot_ref],
        [
            {"type": "nace_identity", "nace_code": snapshot.nace_code, "nace_description": snapshot.nace_description},
            {"type": "hazard_class", "value": snapshot.hazard_class},
            {"type": "training_date", "value": str(getattr(training, "start_date", None) or "")},
            {"type": "company_logo_placeholder", "value": None, "approval_required": True},
        ],
        approval_required=True,
    )
    add(
        "learning_objectives",
        "Eğitimin amacı ve öğrenme hedefleri",
        [topic_ref, "csgb-training-faq-2026"],
        [{"type": "topic_objective", "topic": topic} for topic in topics],
    )
    add(
        "legal_basis",
        "Mevzuat ve sorumluluklar",
        official_source_ids,
        [{"type": "official_source", "source_id": source_id} for source_id in official_source_ids],
    )
    add(
        "nace_identity",
        "İşyeri faaliyeti ve NACE kimliği",
        [snapshot_ref],
        [
            {
                "type": "nace_snapshot",
                "catalog_key": snapshot.catalog_key,
                "nace_code": snapshot.nace_code,
                "nace_description": snapshot.nace_description,
                "hazard_class": snapshot.hazard_class,
                "content_profile_code": snapshot.content_profile_code,
                "catalog_version": snapshot.catalog_version,
                "catalog_hash": snapshot.catalog_hash,
            }
        ],
    )
    add(
        "training_plan",
        "Eğitim planı ve süre",
        [snapshot_ref, "tr-training-regulation-2026", "csgb-training-faq-2026"],
        [
            {"type": "required_duration_hours", "value": snapshot.required_duration_hours},
            {"type": "required_duration_minutes", "value": snapshot.required_duration_minutes},
            {"type": "topic_count", "value": len(topics)},
        ],
    )
    add(
        "foundation_ohs",
        "Temel İSG: haklar, sorumluluklar ve güvenli davranış",
        ["tr-law-6331", exam_ref],
        [{"type": "approved_foundation_questions", "count": foundation_count}],
    )
    add(
        "foundation_ohs",
        "Temel İSG: tehlike, risk, bildirim ve acil durum",
        ["tr-law-6331", "csgb-training-faq-2026", exam_ref],
        [{"type": "approved_foundation_questions", "count": foundation_count}],
    )
    for topic_index, topic in enumerate(topics, start=1):
        add(
            "work_specific_topics",
            topic,
            [topic_ref, risk_ref, "csgb-training-guide"],
            [
                {"type": "frozen_training_topic", "index": topic_index, "value": topic},
                {"type": "technical_content_pending_renderer", "value": True},
            ],
        )
    add(
        "technical_risks",
        "Teknik risk profili",
        [snapshot_ref, risk_ref],
        [{"type": "technical_risk_tag", "value": risk} for risk in risks[:6]],
    )
    add(
        "technical_risks",
        "Özel riskler ve ek değerlendirme",
        [snapshot_ref, risk_ref],
        (
            [{"type": "special_risk", "value": risk} for risk in special_risks]
            if special_risks
            else [{"type": "special_risks_empty", "value": True}]
        ),
    )
    add(
        "control_measures",
        "Risk kontrol hiyerarşisi",
        ["tr-law-6331", risk_ref],
        [{"type": "control_hierarchy", "risk_tags": risks}],
    )
    add(
        "control_measures",
        "İşe özgü güvenli çalışma adımları",
        [topic_ref, risk_ref],
        [{"type": "topic_control_mapping", "topic": topic} for topic in topics],
    )
    add(
        "ppe",
        "Kişisel koruyucu donanım",
        [risk_ref],
        [{"type": "ppe_mapping_pending_specialist_approval", "risk_tags": risks}],
        approval_required=True,
    )
    add(
        "emergency",
        "Acil durum, tahliye ve bildirim",
        ["tr-law-6331", "csgb-training-faq-2026"],
        [
            {"type": "workplace_emergency_placeholder", "field": "assembly_point", "value": None},
            {"type": "workplace_emergency_placeholder", "field": "emergency_contacts", "value": None},
        ],
        approval_required=True,
    )
    add(
        "assessment",
        "Bilgi kontrolü ve değerlendirme",
        [exam_ref],
        [
            {"type": "exam_distribution", "foundation": foundation_count, "work_specific": work_specific_count},
            {"type": "exam_workflow_unchanged", "value": True},
        ],
    )
    add(
        "summary",
        "Özet: kritik güvenli davranışlar",
        [topic_ref, risk_ref],
        [
            {"type": "topic_summary", "values": topics},
            {"type": "risk_summary", "values": risks},
        ],
    )
    add(
        "sources_and_version",
        "Kaynaklar ve sürüm bilgisi",
        official_source_ids + [snapshot_ref, topic_ref, risk_ref, exam_ref],
        [
            {"type": "contract_version", "value": CONTRACT_VERSION},
            {"type": "template_version", "value": TEMPLATE_VERSION},
            {"type": "catalog_version", "value": snapshot.catalog_version},
            {"type": "catalog_hash", "value": snapshot.catalog_hash},
        ],
    )

    layout = contract["layout"]
    if not int(layout["minimum_slide_count"]) <= len(slides) <= int(layout["maximum_slide_count"]):
        raise PresentationContractError(
            f"Manifest slayt sayısı sözleşme aralığı dışında: {len(slides)}."
        )
    positions = [int(slide["position"]) for slide in slides]
    if positions != list(range(1, len(slides) + 1)):
        raise PresentationContractError("Manifest slayt sırası kesintisiz değil.")

    manifest: dict[str, Any] = {
        "manifest_version": "nace-training-presentation-manifest-v1",
        "contract_version": CONTRACT_VERSION,
        "contract_hash": _sha256(contract),
        "template_version": TEMPLATE_VERSION,
        "output_formats": ["pptx", "pdf"],
        "training": {
            "training_id": int(training.id),
            "company_id": int(training.company_id),
            "branch_id": getattr(training, "branch_id", None),
            "title": getattr(training, "title", None),
            "start_date": str(getattr(training, "start_date", None) or ""),
            "end_date": str(getattr(training, "end_date", None) or ""),
        },
        "nace_snapshot": {
            "catalog_key": snapshot.catalog_key,
            "nace_code": snapshot.nace_code,
            "nace_description": snapshot.nace_description,
            "hazard_class": snapshot.hazard_class,
            "content_profile_code": snapshot.content_profile_code,
            "catalog_version": snapshot.catalog_version,
            "catalog_hash": snapshot.catalog_hash,
        },
        "training_topics": topics,
        "technical_risk_tags": risks,
        "special_risks": special_risks,
        "exam_readiness": {
            "policy": exam.get("policy"),
            "foundation": foundation_count,
            "work_specific": work_specific_count,
            "ready": True,
        },
        "source_registry": contract["source_registry"],
        "slides": slides,
        "slide_count": len(slides),
        "approval": {
            "status": "specialist_review_required",
            "required_slide_positions": [
                slide["position"] for slide in slides if slide["approval_required"]
            ],
        },
        "rendering": {
            "supported": False,
            "storage_write": False,
            "reason": "Phase 2 yalnız içerik manifesti ve sözleşme doğrulamasıdır.",
        },
        "core_training_unaffected": True,
    }
    manifest["content_hash"] = _sha256(manifest)
    return manifest
