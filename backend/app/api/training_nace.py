"""Read-only audit API for frozen training NACE classifications."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import TrainingSession, User
from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_nace_classification import (
    classify_training_value,
    resolve_exact_nace,
)

router = APIRouter(prefix="/trainings", tags=["Eğitim NACE Tutarlılığı"])


def _decode(value: str) -> object:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []


def _snapshot_payload(row: TrainingNaceSnapshot) -> dict:
    return {
        "training_id": row.training_id,
        "company_id": row.company_id,
        "branch_id": row.branch_id,
        "catalog_key": row.catalog_key,
        "nace_code": row.nace_code,
        "nace_description": row.nace_description,
        "nace_section_code": row.nace_section_code,
        "nace_section_name": row.nace_section_name,
        "subsector_code": row.subsector_code,
        "activity_group_code": row.activity_group_code,
        "content_profile_code": row.content_profile_code,
        "content_profile_name": row.content_profile_name,
        "hazard_class": row.hazard_class,
        "training_topics": _decode(row.training_topics_json),
        "technical_risk_tags": _decode(row.technical_risk_tags_json),
        "special_risks": _decode(row.special_risks_json),
        "required_duration_minutes": row.required_duration_minutes,
        "required_duration_hours": row.required_duration_hours,
        "classification_status": row.classification_status,
        "catalog_version": row.catalog_version,
        "catalog_hash": row.catalog_hash,
        "created_at": row.created_at,
        "persisted": True,
    }


@router.get("/nace-classification/validate")
def validate_nace_classification(
    sector: str = Query(..., min_length=4, max_length=140),
    user: User = Depends(get_current_user),
):
    """Validate an exact catalog key/code without creating or mutating a record."""
    del user
    try:
        return resolve_exact_nace(sector).to_dict()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{training_id}/nace-classification")
def training_nace_classification(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    training = db.get(TrainingSession, training_id)
    if not training:
        raise HTTPException(404, "Eğitim kaydı bulunamadı.")
    ensure_company_access(db, user, training.company_id)

    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(
            TrainingNaceSnapshot.training_id == training_id
        )
    )
    if snapshot:
        return _snapshot_payload(snapshot)

    # Read-only legacy view. It does not infer or persist an exact NACE code.
    classification = classify_training_value(
        training.sector, hazard_class=training.hazard_class
    )
    return {
        "training_id": training.id,
        "company_id": training.company_id,
        "branch_id": training.branch_id,
        **classification.to_dict(),
        "persisted": False,
    }
