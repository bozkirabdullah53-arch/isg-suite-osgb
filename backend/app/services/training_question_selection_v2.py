"""Snapshot-aware, fail-closed question selection for verified NACE trainings.

Legacy records keep the historical selector. When
``TRAINING_EXACT_NACE_EXAM_STRICT=true`` and a persisted/verified NACE snapshot
exists, new exam snapshots use five fixed foundational questions plus fifteen
source-controlled questions generated from the snapshot's five frozen
work-specific topics. Existing exam snapshots are never rewritten.
"""
from __future__ import annotations

import os
import sys
from functools import wraps
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import TrainingSession
from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_exact_question_factory import (
    EXACT_NACE_POLICY,
    create_exact_nace_exam_snapshot,
    exact_question_readiness,
)

STRICT_ENV = "TRAINING_EXACT_NACE_EXAM_STRICT"
_CONTEXT_ATTR = "_verified_exact_nace_exam_context_v2"

_legacy_candidate_buckets: Callable | None = None
_legacy_curated_buckets: Callable | None = None
_legacy_create_exam_snapshot: Callable | None = None
_legacy_question_bank_readiness: Callable | None = None


def exact_nace_exam_strict_active() -> bool:
    value = str(os.getenv(STRICT_ENV, "false") or "").strip().casefold()
    return value in {"1", "true", "yes", "on"}


def _verified_snapshot_context(
    db: Session, training: TrainingSession
) -> dict[str, str] | None:
    if not getattr(training, "id", None):
        return None
    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(
            TrainingNaceSnapshot.training_id == training.id
        )
    )
    if snapshot is None or snapshot.classification_status != "verified":
        return None
    required = {
        "hazard": str(snapshot.hazard_class or "").strip(),
        "sector": str(snapshot.content_profile_code or "").strip(),
        "sector_code": str(snapshot.catalog_key or "").strip(),
        "nace": str(snapshot.nace_code or "").strip(),
    }
    if not all(required.values()) or not required["sector_code"].startswith("nace_"):
        return None
    return required


def _question_code(row: Any) -> str:
    if isinstance(row, dict):
        return str(row.get("question_code") or "")
    return str(getattr(row, "question_code", "") or "")


def _bucket_counts(buckets: dict[str, list[Any]]) -> dict[str, int]:
    return {
        name: len({_question_code(row) for row in rows if _question_code(row)})
        for name, rows in buckets.items()
    }


def _combined_counts(
    database: dict[str, list[Any]], curated: dict[str, list[Any]]
) -> dict[str, int]:
    names = set(database) | set(curated)
    return {
        name: len(
            {_question_code(row) for row in database.get(name, []) if _question_code(row)}
            | {_question_code(row) for row in curated.get(name, []) if _question_code(row)}
        )
        for name in names
    }


def _strict_database_buckets(
    question_bank, db: Session, training: TrainingSession, ctx: dict[str, str]
):
    rows = question_bank._published_questions_for_training(db, training)
    return question_bank._buckets_for_context(rows, ctx)


def _strict_curated_buckets(question_bank, ctx: dict[str, str]) -> dict[str, list[dict]]:
    """Audit-only comparison without cross-sector aliases or genel_uretim."""
    common = list(question_bank._curated_pack("common.json"))
    hazard_file = question_bank._CURATED_HAZARD_PACKS.get(ctx["hazard"])
    technical = list(question_bank._curated_pack(hazard_file)) if hazard_file else []
    sector: list[dict] = []
    for file_name in question_bank._CURATED_SECTOR_PACKS:
        for item in question_bank._curated_pack(file_name):
            if any(
                (
                    scope.get("type") == "sector"
                    and question_bank.sector_scope_matches(
                        ctx, str(scope.get("value") or "")
                    )
                )
                or (
                    scope.get("type") == "nace"
                    and question_bank.nace_scope_matches(
                        ctx["nace"], str(scope.get("value") or "")
                    )
                )
                for scope in item["scopes"]
            ):
                sector.append(item)
    return {"common": common, "technical": technical, "sector": sector}


def _legacy_ready(question_bank, counts: dict[str, int]) -> bool:
    return all(
        counts.get(name, 0) >= needed
        for name, needed in question_bank.BUCKET_TARGETS.items()
    )


def question_selection_audit(db: Session, training: TrainingSession) -> dict[str, Any]:
    """Compare historical alias selection with exact-NACE snapshot selection."""
    from app.services import training_question_bank as question_bank

    ctx = _verified_snapshot_context(db, training)
    legacy_candidate = _legacy_candidate_buckets or question_bank._candidate_buckets
    legacy_curated = _legacy_curated_buckets or question_bank._curated_buckets

    previous_ctx = getattr(training, _CONTEXT_ATTR, None)
    if hasattr(training, _CONTEXT_ATTR):
        delattr(training, _CONTEXT_ATTR)
    try:
        legacy_db = legacy_candidate(db, training)
        legacy_curated_rows = legacy_curated(training)
    finally:
        if previous_ctx is not None:
            setattr(training, _CONTEXT_ATTR, previous_ctx)

    legacy_combined = _combined_counts(legacy_db, legacy_curated_rows)
    if ctx is None:
        return {
            "training_id": training.id,
            "strict_flag_enabled": exact_nace_exam_strict_active(),
            "selection_mode": "legacy_unverified",
            "verified_snapshot": False,
            "context": None,
            "legacy": {
                "database": _bucket_counts(legacy_db),
                "curated": _bucket_counts(legacy_curated_rows),
                "combined": legacy_combined,
                "ready": _legacy_ready(question_bank, legacy_combined),
            },
            "exact_factory": None,
            "strict_activation_blocked": True,
            "reason": "Eğitim için persisted ve verified NACE snapshot bulunmuyor.",
        }

    strict_db = _strict_database_buckets(question_bank, db, training, ctx)
    strict_curated = _strict_curated_buckets(question_bank, ctx)
    strict_combined = _combined_counts(strict_db, strict_curated)
    legacy_ready = _legacy_ready(question_bank, legacy_combined)
    factory = exact_question_readiness(db, training)

    legacy_sector_codes = sorted(
        {
            _question_code(row)
            for row in legacy_curated_rows.get("sector", [])
            if _question_code(row)
        }
    )
    strict_sector_codes = sorted(
        {
            _question_code(row)
            for row in strict_curated.get("sector", [])
            if _question_code(row)
        }
    )
    alias_only_codes = sorted(set(legacy_sector_codes) - set(strict_sector_codes))

    return {
        "training_id": training.id,
        "strict_flag_enabled": exact_nace_exam_strict_active(),
        "selection_mode": (
            "exact_nace_snapshot_5_plus_15"
            if exact_nace_exam_strict_active()
            else "legacy_compatibility"
        ),
        "verified_snapshot": True,
        "context": ctx,
        "legacy": {
            "database": _bucket_counts(legacy_db),
            "curated": _bucket_counts(legacy_curated_rows),
            "combined": legacy_combined,
            "ready": legacy_ready,
        },
        "strict_without_alias": {
            "database": _bucket_counts(strict_db),
            "curated": _bucket_counts(strict_curated),
            "combined": strict_combined,
        },
        "exact_factory": factory,
        "strict_activation_blocked": not bool(factory["ready"]),
        "legacy_ready_but_strict_blocked": legacy_ready and not bool(factory["ready"]),
        "alias_only_sector_question_count": len(alias_only_codes),
        "alias_only_sector_question_codes": alias_only_codes[:50],
        "selection_policy": EXACT_NACE_POLICY,
    }


def install_exact_nace_question_selection() -> dict[str, str]:
    """Install idempotent wrappers after historical runtime patches."""
    global _legacy_candidate_buckets, _legacy_curated_buckets
    global _legacy_create_exam_snapshot, _legacy_question_bank_readiness

    from app.services import training_question_bank as question_bank

    current_candidate = question_bank._candidate_buckets
    if getattr(current_candidate, "_exact_nace_snapshot_selection_active", False):
        return {
            "candidate_buckets": "already-active",
            "curated_buckets": "already-active",
            "create_exam_snapshot": "already-active",
            "question_bank_readiness": "already-active",
            "strict_flag": str(exact_nace_exam_strict_active()).lower(),
        }

    _legacy_candidate_buckets = current_candidate
    _legacy_curated_buckets = question_bank._curated_buckets
    _legacy_create_exam_snapshot = question_bank.create_exam_snapshot
    _legacy_question_bank_readiness = question_bank.question_bank_readiness

    @wraps(current_candidate)
    def snapshot_candidate_buckets(db: Session, training: TrainingSession):
        ctx = _verified_snapshot_context(db, training)
        if not exact_nace_exam_strict_active() or ctx is None:
            if hasattr(training, _CONTEXT_ATTR):
                delattr(training, _CONTEXT_ATTR)
            return _legacy_candidate_buckets(db, training)
        setattr(training, _CONTEXT_ATTR, ctx)
        return _strict_database_buckets(question_bank, db, training, ctx)

    snapshot_candidate_buckets._exact_nace_snapshot_selection_active = True
    question_bank._candidate_buckets = snapshot_candidate_buckets

    @wraps(_legacy_curated_buckets)
    def snapshot_curated_buckets(training: TrainingSession):
        ctx = getattr(training, _CONTEXT_ATTR, None)
        if exact_nace_exam_strict_active() and isinstance(ctx, dict):
            return _strict_curated_buckets(question_bank, ctx)
        return _legacy_curated_buckets(training)

    snapshot_curated_buckets._exact_nace_snapshot_selection_active = True
    question_bank._curated_buckets = snapshot_curated_buckets

    @wraps(_legacy_question_bank_readiness)
    def snapshot_readiness(db: Session, training: TrainingSession):
        if exact_nace_exam_strict_active() and _verified_snapshot_context(db, training):
            return exact_question_readiness(db, training)
        return _legacy_question_bank_readiness(db, training)

    snapshot_readiness._exact_nace_snapshot_selection_active = True
    question_bank.question_bank_readiness = snapshot_readiness

    @wraps(_legacy_create_exam_snapshot)
    def snapshot_create_exam(*args, **kwargs):
        db = kwargs.get("db") or (args[0] if args else None)
        training = kwargs.get("training")
        if (
            exact_nace_exam_strict_active()
            and db is not None
            and training is not None
            and _verified_snapshot_context(db, training)
        ):
            return create_exact_nace_exam_snapshot(
                db,
                training=training,
                created_by_id=int(kwargs["created_by_id"]),
            )
        return _legacy_create_exam_snapshot(*args, **kwargs)

    snapshot_create_exam._exact_nace_snapshot_selection_active = True
    question_bank.create_exam_snapshot = snapshot_create_exam

    for module_name in (
        "app.services.training_exam_pdf",
        "app.api.training_question_bank",
    ):
        module = sys.modules.get(module_name)
        if module is not None:
            if hasattr(module, "create_exam_snapshot"):
                setattr(module, "create_exam_snapshot", snapshot_create_exam)
            if hasattr(module, "question_bank_readiness"):
                setattr(module, "question_bank_readiness", snapshot_readiness)

    return {
        "candidate_buckets": "active",
        "curated_buckets": "active",
        "create_exam_snapshot": "active",
        "question_bank_readiness": "active",
        "strict_flag": str(exact_nace_exam_strict_active()).lower(),
    }
