"""Append-only persistence service for NACE presentation draft versions.

Creation is feature-flag gated and freezes the Phase 2 manifest plus all source
classification fields. The service never renders or writes a file. Existing
versions may be listed/read even when the optional feature is disabled so that
historical evidence remains accessible.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import nace_training_presentation_active
from app.models.entities import TrainingSession
from app.models.training_nace import TrainingNaceSnapshot
from app.models.training_presentation import TrainingPresentationVersion
from app.services.training_exact_question_factory import exact_question_readiness
from app.services.training_presentation_contract import (
    PresentationContractError,
    build_presentation_manifest_preview,
)


class PresentationVersionError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_value(raw: str | None, fallback: object) -> object:
    try:
        return json.loads(raw or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def version_payload(row: TrainingPresentationVersion, *, include_manifest: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": row.id,
        "training_id": row.training_id,
        "company_id": row.company_id,
        "branch_id": row.branch_id,
        "nace_snapshot_id": row.nace_snapshot_id,
        "version": row.version,
        "status": row.status,
        "contract_version": row.contract_version,
        "contract_hash": row.contract_hash,
        "template_version": row.template_version,
        "manifest_version": row.manifest_version,
        "manifest_hash": row.manifest_hash,
        "nace": {
            "catalog_key": row.catalog_key,
            "nace_code": row.nace_code,
            "nace_description": row.nace_description,
            "hazard_class": row.hazard_class,
            "content_profile_code": row.content_profile_code,
            "catalog_version": row.catalog_version,
            "catalog_hash": row.catalog_hash,
        },
        "source_data": {
            "training_topics": _json_value(row.training_topics_json, []),
            "technical_risk_tags": _json_value(row.technical_risk_tags_json, []),
            "special_risks": _json_value(row.special_risks_json, []),
        },
        "outputs": {
            "formats": _json_value(row.output_formats_json, []),
            "primary": row.primary_output_format,
            "pptx": {
                "storage_key": row.pptx_storage_key,
                "file_hash": row.pptx_file_hash,
                "file_size": row.pptx_file_size,
                "content_type": row.pptx_content_type,
            },
            "pdf": {
                "storage_key": row.pdf_storage_key,
                "file_hash": row.pdf_file_hash,
                "file_size": row.pdf_file_size,
                "content_type": row.pdf_content_type,
            },
        },
        "created_by_id": row.created_by_id,
        "approved_by_id": row.approved_by_id,
        "failure": {
            "code": row.failure_code,
            "detail": row.failure_detail,
        },
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "generated_at": row.generated_at,
        "approved_at": row.approved_at,
        "failed_at": row.failed_at,
        "archived_at": row.archived_at,
        "read_only_source_snapshot": True,
        "renderer_available": True,
        "storage_write": False,
    }
    if include_manifest:
        payload["manifest"] = _json_value(row.manifest_json, {})
        payload["source_snapshot"] = _json_value(row.source_snapshot_json, {})
    return payload


def list_presentation_versions(
    db: Session,
    *,
    training_id: int,
) -> list[TrainingPresentationVersion]:
    return list(
        db.scalars(
            select(TrainingPresentationVersion)
            .where(TrainingPresentationVersion.training_id == training_id)
            .order_by(TrainingPresentationVersion.version.desc())
        ).all()
    )


def get_presentation_version(
    db: Session,
    *,
    training_id: int,
    version_id: int,
) -> TrainingPresentationVersion | None:
    return db.scalar(
        select(TrainingPresentationVersion).where(
            TrainingPresentationVersion.id == version_id,
            TrainingPresentationVersion.training_id == training_id,
        )
    )


def create_draft_version(
    db: Session,
    *,
    training: TrainingSession,
    created_by_id: int | None,
) -> TrainingPresentationVersion:
    """Create one new immutable draft; no render, file or object-store write."""
    if not nace_training_presentation_active(getattr(training, "company_id", None)):
        raise PresentationVersionError(
            "pilot_access_denied",
            "NACE eğitim sunumu bu şirket için kontrollü pilot erişimine açık değildir.",
        )

    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(
            TrainingNaceSnapshot.training_id == training.id
        )
    )
    try:
        manifest = build_presentation_manifest_preview(
            training=training,
            snapshot=snapshot,
            exam_readiness=exact_question_readiness(db, training),
        )
    except PresentationContractError as exc:
        raise PresentationVersionError("manifest_not_ready", str(exc)) from exc
    if snapshot is None:
        raise PresentationVersionError(
            "verified_snapshot_missing",
            "Doğrulanmış NACE snapshot bulunmuyor.",
        )

    current_max = db.scalar(
        select(func.max(TrainingPresentationVersion.version)).where(
            TrainingPresentationVersion.training_id == training.id
        )
    )
    next_version = int(current_max or 0) + 1
    manifest_hash = str(manifest.get("content_hash") or "")
    if len(manifest_hash) != 64:
        raise PresentationVersionError(
            "invalid_manifest_hash",
            "Sunum manifest hash'i geçersiz.",
        )

    row = TrainingPresentationVersion(
        training_id=int(training.id),
        company_id=int(training.company_id),
        branch_id=getattr(training, "branch_id", None),
        nace_snapshot_id=getattr(snapshot, "id", None),
        version=next_version,
        status="draft",
        contract_version=str(manifest["contract_version"]),
        contract_hash=str(manifest["contract_hash"]),
        template_version=str(manifest["template_version"]),
        manifest_version=str(manifest["manifest_version"]),
        manifest_json=_canonical_json(manifest),
        manifest_hash=manifest_hash,
        catalog_key=str(snapshot.catalog_key),
        nace_code=str(snapshot.nace_code),
        nace_description=str(snapshot.nace_description),
        hazard_class=str(snapshot.hazard_class),
        content_profile_code=str(snapshot.content_profile_code),
        catalog_version=str(snapshot.catalog_version),
        catalog_hash=str(snapshot.catalog_hash),
        source_snapshot_json=str(snapshot.source_snapshot_json),
        training_topics_json=str(snapshot.training_topics_json),
        technical_risk_tags_json=str(snapshot.technical_risk_tags_json),
        special_risks_json=str(snapshot.special_risks_json),
        output_formats_json=_canonical_json(manifest.get("output_formats") or []),
        primary_output_format="pptx",
        created_by_id=created_by_id,
    )
    db.add(row)
    db.flush()
    return row
