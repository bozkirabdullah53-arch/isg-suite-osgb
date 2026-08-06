"""Read-only readiness for the optional NACE-aligned training presentation.

Phase 1 deliberately creates no database record, presentation file or storage
write. The service only evaluates the existing frozen NACE snapshot and exact
exam readiness. Core training, exam, PDF and certificate workflows must never
be blocked by this optional feature.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import nace_training_presentation_active
from app.models.entities import TrainingSession
from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_exact_question_factory import exact_question_readiness

READINESS_VERSION = "nace-training-presentation-readiness-v1"
TEMPLATE_CONTRACT_VERSION = None
TEMPLATE_CONTRACT_STATUS = "pending_specialist_approval"


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


def build_presentation_readiness_payload(
    *,
    training: TrainingSession,
    snapshot: TrainingNaceSnapshot | None,
    exam_readiness: dict[str, Any] | None,
    enabled: bool,
) -> dict[str, Any]:
    """Build a deterministic, side-effect-free readiness response."""
    topics = _json_list(snapshot.training_topics_json) if snapshot else []
    technical_risks = _json_list(snapshot.technical_risk_tags_json) if snapshot else []
    special_risks = _json_list(snapshot.special_risks_json) if snapshot else []
    classification_status = (
        str(snapshot.classification_status or "legacy_unverified")
        if snapshot
        else "legacy_unverified"
    )
    exact_nace = bool(
        snapshot
        and classification_status == "verified"
        and str(snapshot.catalog_key or "").startswith("nace_")
        and str(snapshot.nace_code or "").strip()
    )
    five_topics = len(topics) == 5
    technical_risks_ready = len(technical_risks) > 0
    exam = dict(exam_readiness or {})
    exam_ready = bool(exam.get("ready"))
    cancelled = _status_value(training) == "cancelled"

    checks = [
        {
            "code": "feature_flag",
            "label": "Sunum özelliği",
            "ok": enabled,
            "detail": (
                "Özellik kontrollü test için açık."
                if enabled
                else "Güvenli varsayılan nedeniyle kapalı; mevcut eğitim akışı aynen devam eder."
            ),
        },
        {
            "code": "verified_nace_snapshot",
            "label": "Doğrulanmış NACE snapshot",
            "ok": exact_nace,
            "detail": (
                f"{snapshot.nace_code} · {snapshot.nace_description}"
                if exact_nace
                else "Persisted ve verified tam NACE snapshot bulunmuyor; NACE tahmini yapılmaz."
            ),
        },
        {
            "code": "five_training_topics",
            "label": "Beş işe özgü eğitim konusu",
            "ok": five_topics,
            "detail": (
                "Dondurulmuş beş konu hazır."
                if five_topics
                else f"Beklenen 5 konu, bulunan {len(topics)}."
            ),
        },
        {
            "code": "technical_risks",
            "label": "Teknik risk etiketleri",
            "ok": technical_risks_ready,
            "detail": (
                f"{len(technical_risks)} teknik risk etiketi hazır."
                if technical_risks_ready
                else "Teknik risk etiketi bulunmuyor."
            ),
        },
        {
            "code": "exact_exam_readiness",
            "label": "NACE uyumlu sınav içeriği",
            "ok": exam_ready,
            "detail": (
                "Mevcut 5 temel + 15 işe özgü sınav içeriği hazır."
                if exam_ready
                else str(exam.get("reason") or "Exact-NACE sınav hazırlığı tamamlanmamış.")
            ),
        },
        {
            "code": "training_not_cancelled",
            "label": "Eğitim durumu",
            "ok": not cancelled,
            "detail": (
                "Eğitim iptal edilmemiş."
                if not cancelled
                else "İptal edilmiş eğitim için yeni sunum üretilmez."
            ),
        },
        {
            "code": "template_contract",
            "label": "Uzman onaylı sunum şablonu",
            "ok": False,
            "detail": "Çıktı biçimi ve slayt içerik sözleşmesi henüz uzman onayından geçmedi.",
        },
    ]

    blockers = [
        {"code": item["code"], "detail": item["detail"]}
        for item in checks
        if not item["ok"]
    ]
    warnings: list[dict[str, str]] = []
    if exact_nace and not special_risks:
        warnings.append(
            {
                "code": "special_risks_empty",
                "detail": "Özel risk listesi boş; bu durum içerik sözleşmesinde kapsam dışı veya eksik olarak kararlaştırılmalı.",
            }
        )

    return {
        "readiness_version": READINESS_VERSION,
        "training_id": int(training.id),
        "company_id": int(training.company_id),
        "branch_id": getattr(training, "branch_id", None),
        "enabled": enabled,
        "visible": enabled,
        "read_only": True,
        "generation_supported": False,
        "generation_allowed": False,
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
            "status": TEMPLATE_CONTRACT_STATUS,
            "version": TEMPLATE_CONTRACT_VERSION,
            "output_formats": [],
            "tracking_issue": 76,
        },
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "next_action": (
            "Özellik kapalı; mevcut eğitim/sınav/PDF/sertifika işlemlerine devam edin."
            if not enabled
            else "Sunum üretimi için önce GitHub #76 içerik ve şablon sözleşmesini uzman onayına tamamlayın."
        ),
    }


def training_presentation_readiness(
    db: Session,
    *,
    training: TrainingSession,
) -> dict[str, Any]:
    """Read existing records only; never commit, flush, write a file or upload."""
    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(
            TrainingNaceSnapshot.training_id == training.id
        )
    )
    exam = exact_question_readiness(db, training)
    return build_presentation_readiness_payload(
        training=training,
        snapshot=snapshot,
        exam_readiness=exam,
        enabled=nace_training_presentation_active(),
    )
