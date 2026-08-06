"""Read-only readiness for the optional NACE-aligned training presentation."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import nace_training_presentation_active
from app.models.entities import TrainingSession
from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_exact_question_factory import exact_question_readiness
from app.services.training_presentation_contract import (
    CONTRACT_VERSION,
    TEMPLATE_VERSION,
    PresentationContractError,
    presentation_contract_payload,
)
from app.services.training_presentation_renderer import RENDERER_VERSION

READINESS_VERSION = "nace-training-presentation-readiness-v3"


def _json_list(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _status_value(training: TrainingSession) -> str:
    raw = getattr(training, "status", "")
    return str(getattr(raw, "value", raw) or "").strip().lower()


def _contract_state() -> dict[str, Any]:
    try:
        payload = presentation_contract_payload()
    except PresentationContractError as exc:
        return {
            "ok": False,
            "status": "invalid",
            "version": None,
            "template_version": None,
            "contract_hash": None,
            "output_formats": [],
            "detail": str(exc),
        }
    outputs = payload.get("outputs") or {}
    return {
        "ok": True,
        "status": str(payload.get("status") or "approved_for_implementation"),
        "version": payload.get("contract_version"),
        "template_version": payload.get("template_version"),
        "contract_hash": payload.get("contract_hash"),
        "output_formats": [outputs.get("primary"), *(outputs.get("companions") or [])],
        "detail": "PPTX ana ve PDF yardımcı çıktı için içerik sözleşmesi onaylandı.",
    }


def build_presentation_readiness_payload(
    *,
    training: TrainingSession,
    snapshot: TrainingNaceSnapshot | None,
    exam_readiness: dict[str, Any] | None,
    enabled: bool,
) -> dict[str, Any]:
    topics = _json_list(snapshot.training_topics_json) if snapshot else []
    technical_risks = _json_list(snapshot.technical_risk_tags_json) if snapshot else []
    special_risks = _json_list(snapshot.special_risks_json) if snapshot else []
    classification_status = (
        str(snapshot.classification_status or "legacy_unverified")
        if snapshot else "legacy_unverified"
    )
    exact_nace = bool(
        snapshot
        and classification_status == "verified"
        and str(snapshot.catalog_key or "").startswith("nace_")
        and str(snapshot.nace_code or "").strip()
    )
    five_topics = len(topics) == 5
    technical_risks_ready = bool(technical_risks)
    exam = dict(exam_readiness or {})
    exam_ready = bool(exam.get("ready"))
    cancelled = _status_value(training) == "cancelled"
    contract = _contract_state()

    checks = [
        {
            "code": "feature_flag",
            "label": "Sunum özelliği",
            "ok": enabled,
            "detail": "Özellik kontrollü kullanım için açık." if enabled else "Güvenli varsayılan nedeniyle kapalı; mevcut eğitim akışı aynen devam eder.",
        },
        {
            "code": "verified_nace_snapshot",
            "label": "Doğrulanmış NACE snapshot",
            "ok": exact_nace,
            "detail": f"{snapshot.nace_code} · {snapshot.nace_description}" if exact_nace else "Persisted ve verified tam NACE snapshot bulunmuyor; NACE tahmini yapılmaz.",
        },
        {
            "code": "five_training_topics",
            "label": "Beş işe özgü eğitim konusu",
            "ok": five_topics,
            "detail": "Dondurulmuş beş konu hazır." if five_topics else f"Beklenen 5 konu, bulunan {len(topics)}.",
        },
        {
            "code": "technical_risks",
            "label": "Teknik risk etiketleri",
            "ok": technical_risks_ready,
            "detail": f"{len(technical_risks)} teknik risk etiketi hazır." if technical_risks_ready else "Teknik risk etiketi bulunmuyor.",
        },
        {
            "code": "exact_exam_readiness",
            "label": "NACE uyumlu sınav içeriği",
            "ok": exam_ready,
            "detail": "Mevcut 5 temel + 15 işe özgü sınav içeriği hazır." if exam_ready else str(exam.get("reason") or "Exact-NACE sınav hazırlığı tamamlanmamış."),
        },
        {
            "code": "training_not_cancelled",
            "label": "Eğitim durumu",
            "ok": not cancelled,
            "detail": "Eğitim iptal edilmemiş." if not cancelled else "İptal edilmiş eğitim için yeni sunum üretilmez.",
        },
        {
            "code": "template_contract",
            "label": "Uzman onaylı içerik ve şablon sözleşmesi",
            "ok": bool(contract["ok"]),
            "detail": str(contract["detail"]),
        },
        {
            "code": "presentation_renderer",
            "label": "PPTX/PDF üretim servisi",
            "ok": True,
            "detail": f"Deterministik PPTX ve PDF renderer hazır: {RENDERER_VERSION}.",
        },
    ]
    blockers = [
        {"code": item["code"], "detail": item["detail"]}
        for item in checks if not item["ok"]
    ]
    warnings: list[dict[str, str]] = []
    if exact_nace and not special_risks:
        warnings.append({
            "code": "special_risks_empty",
            "detail": "Özel risk listesi boş; manifestte açıkça boş olarak gösterilir ve risk uydurulmaz.",
        })
    generation_allowed = enabled and not blockers

    return {
        "readiness_version": READINESS_VERSION,
        "training_id": int(training.id),
        "company_id": int(training.company_id),
        "branch_id": getattr(training, "branch_id", None),
        "enabled": enabled,
        "visible": enabled,
        "read_only": True,
        "manifest_preview_supported": bool(contract["ok"]),
        "generation_supported": True,
        "generation_allowed": generation_allowed,
        "renderer_version": RENDERER_VERSION,
        "core_training_unaffected": True,
        "classification": {
            "persisted": snapshot is not None,
            "status": classification_status,
            "catalog_key": snapshot.catalog_key if snapshot else None,
            "nace_code": snapshot.nace_code if snapshot else None,
            "nace_description": snapshot.nace_description if snapshot else None,
            "hazard_class": snapshot.hazard_class if snapshot else getattr(training, "hazard_class", None),
            "content_profile_code": snapshot.content_profile_code if snapshot else None,
            "catalog_version": snapshot.catalog_version if snapshot else None,
            "catalog_hash": snapshot.catalog_hash if snapshot else None,
        },
        "source_data": {
            "training_topics": topics,
            "technical_risk_tags": technical_risks,
            "special_risks": special_risks,
            "exam_readiness": exam,
        },
        "template_contract": {
            "status": contract["status"],
            "version": contract["version"] or CONTRACT_VERSION,
            "template_version": contract["template_version"] or TEMPLATE_VERSION,
            "contract_hash": contract["contract_hash"],
            "output_formats": [item for item in contract["output_formats"] if item],
            "tracking_issue": 76,
        },
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "next_action": (
            "Özellik kapalı; mevcut eğitim/sınav/PDF/sertifika işlemlerine devam edin."
            if not enabled else (
                "Hazırlık tamamlandı. İçerik önizlemesi açabilir veya yeni bir sunum sürümü oluşturabilirsiniz."
                if generation_allowed else "Eksik hazırlık kontrollerini tamamlayın; eğitim ve belge işlemleri etkilenmez."
            )
        ),
    }


def training_presentation_readiness(
    db: Session,
    *,
    training: TrainingSession,
) -> dict[str, Any]:
    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(
            TrainingNaceSnapshot.training_id == training.id
        )
    )
    return build_presentation_readiness_payload(
        training=training,
        snapshot=snapshot,
        exam_readiness=exact_question_readiness(db, training),
        enabled=nace_training_presentation_active(),
    )
