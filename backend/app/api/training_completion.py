"""Verified training result entry, finalization, preflight and public verification."""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import (
    AuditLog,
    Company,
    Employee,
    TrainingParticipant,
    TrainingSession,
    TrainingStatus,
    User,
    UserRole,
)
from app.schemas.training import TrainingVerifyResponse
from app.services.training_completion import (
    completion_preflight,
    completion_strict_active,
    finalize_training_results,
    verified_snapshot,
)

router = APIRouter(prefix="/trainings", tags=["Eğitim Tamamlama ve Belgelendirme"])
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)


class ParticipantResultUpdate(BaseModel):
    attended: bool
    score: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def absent_has_no_score(self):
        if not self.attended and self.score is not None:
            raise ValueError("Katılmayan personel için sınav puanı girilemez.")
        return self


class ParticipantResultBulkItem(ParticipantResultUpdate):
    participant_id: int = Field(gt=0)


class ParticipantResultBulkUpdate(BaseModel):
    items: list[ParticipantResultBulkItem] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_participants(self):
        ids = [item.participant_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Aynı katılımcı sonuç listesinde birden fazla kez bulunamaz.")
        return self


def _training(db: Session, training_id: int) -> TrainingSession:
    row = db.scalar(
        select(TrainingSession)
        .options(selectinload(TrainingSession.participants))
        .where(TrainingSession.id == training_id)
    )
    if row is None:
        raise HTTPException(404, "Eğitim kaydı bulunamadı.")
    return row


def _participant(training: TrainingSession, participant_id: int) -> TrainingParticipant:
    row = next((item for item in training.participants if item.id == participant_id), None)
    if row is None:
        raise HTTPException(404, "Katılımcı bu eğitim kaydında bulunamadı.")
    return row


def _apply_result(training: TrainingSession, participant: TrainingParticipant, payload) -> None:
    participant.attended = bool(payload.attended)
    if not participant.attended:
        participant.score = None
        participant.successful = False
    else:
        participant.score = payload.score
        if payload.score is None or training.passing_score is None:
            participant.successful = None
        else:
            participant.successful = int(payload.score) >= int(training.passing_score)
    # Any result edit invalidates earlier final confirmation until re-finalized.
    training.attendance_verified = False
    training.success_verified = False
    if training.status == TrainingStatus.COMPLETED:
        training.status = TrainingStatus.PLANNED


def _audit(
    db: Session,
    *,
    user: User,
    training: TrainingSession,
    action: str,
    description: str,
    payload: dict,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id,
            company_id=training.company_id,
            action=action,
            entity_type="training_session",
            entity_id=str(training.id),
            description=description,
            module="training",
            new_value=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        )
    )


@router.get("/{training_id}/completion-preflight")
def training_completion_preflight(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    training = _training(db, training_id)
    ensure_company_access(db, user, training.company_id)
    return completion_preflight(db, training)


@router.patch("/{training_id}/participants/{participant_id}/result")
def update_participant_result(
    training_id: int,
    participant_id: int,
    payload: ParticipantResultUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    training = _training(db, training_id)
    ensure_company_access(db, user, training.company_id)
    if training.status == TrainingStatus.CANCELLED:
        raise HTTPException(409, "İptal edilmiş eğitimde sonuç değiştirilemez.")
    participant = _participant(training, participant_id)
    _apply_result(training, participant, payload)
    _audit(
        db,
        user=user,
        training=training,
        action="training_participant_result_updated",
        description="Katılımcı eğitim sonucu güncellendi; önceki final doğrulama kaldırıldı.",
        payload={
            "participant_id": participant.id,
            "employee_id": participant.employee_id,
            "attended": participant.attended,
            "score": participant.score,
            "successful": participant.successful,
        },
    )
    db.commit()
    return completion_preflight(db, _training(db, training_id))


@router.put("/{training_id}/participant-results")
def update_participant_results_bulk(
    training_id: int,
    payload: ParticipantResultBulkUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    training = _training(db, training_id)
    ensure_company_access(db, user, training.company_id)
    if training.status == TrainingStatus.CANCELLED:
        raise HTTPException(409, "İptal edilmiş eğitimde sonuç değiştirilemez.")
    current = {participant.id: participant for participant in training.participants}
    unknown = [item.participant_id for item in payload.items if item.participant_id not in current]
    if unknown:
        raise HTTPException(422, f"Eğitime ait olmayan katılımcı kimlikleri: {unknown[:10]}")
    for item in payload.items:
        _apply_result(training, current[item.participant_id], item)
    _audit(
        db,
        user=user,
        training=training,
        action="training_participant_results_bulk_updated",
        description="Katılımcı sonuçları toplu güncellendi; önceki final doğrulama kaldırıldı.",
        payload={"updated_count": len(payload.items)},
    )
    db.commit()
    return completion_preflight(db, _training(db, training_id))


@router.post("/{training_id}/finalize")
def finalize_training(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    training = _training(db, training_id)
    ensure_company_access(db, user, training.company_id)
    try:
        result = finalize_training_results(db, training)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    _audit(
        db,
        user=user,
        training=training,
        action="training_results_finalized",
        description="Katılım ve başarı sonuçları doğrulanarak eğitim tamamlandı.",
        payload={
            "eligible_count": result["eligible_count"],
            "ineligible_count": result["ineligible_count"],
            "passing_score": result.get("passing_score"),
        },
    )
    db.commit()
    return completion_preflight(db, _training(db, training_id))


# This route is registered before the legacy verify route. Legacy records retain
# the old participant visibility; verified records expose only eligible holders.
@router.get(
    "/verify/{code}",
    response_model=TrainingVerifyResponse,
    response_model_exclude_none=True,
)
def verify_completed_training(code: str, db: Session = Depends(get_db)):
    clean = (code or "").strip().upper()
    if not clean or len(clean) < 8:
        return TrainingVerifyResponse(
            valid=False,
            verification_code=clean or "",
            message="Geçersiz doğrulama kodu.",
        )
    training = db.scalar(
        select(TrainingSession)
        .options(selectinload(TrainingSession.participants))
        .where(TrainingSession.verification_code == clean)
    )
    if training is None:
        return TrainingVerifyResponse(
            valid=False,
            verification_code=clean,
            message="Bu kodla eşleşen eğitim belgesi bulunamadı.",
        )

    strict = completion_strict_active() and verified_snapshot(db, training) is not None
    if strict:
        preflight = completion_preflight(db, training)
        eligible_ids = {
            int(item["participant_id"])
            for item in preflight["participants"]
            if item["eligible"]
        }
        visible = [p for p in training.participants if p.id in eligible_ids]
        valid = bool(preflight["ready_for_certificates"] and visible)
        if not valid:
            return TrainingVerifyResponse(
                valid=False,
                verification_code=clean,
                title=training.title,
                message="Eğitim kaydı mevcut ancak doğrulanmış belge almaya hak kazanan katılımcı bulunmuyor.",
            )
    else:
        visible = list(training.participants)
        valid = True

    employee_ids = [p.employee_id for p in visible]
    employees = {
        row.id: row
        for row in db.scalars(
            select(Employee).where(Employee.id.in_(employee_ids or [-1]))
        ).all()
    }
    participants = [
        {
            "full_name": employees[p.employee_id].full_name
            if p.employee_id in employees
            else f"#{p.employee_id}",
            "certificate_number": p.certificate_number,
        }
        for p in visible
    ]
    company = db.get(Company, training.company_id)
    return TrainingVerifyResponse(
        valid=valid,
        verification_code=clean,
        title=training.title,
        company_name=company.name if company else None,
        start_date=training.start_date,
        end_date=training.end_date,
        hazard_class=training.hazard_class,
        duration_hours=training.duration_hours,
        instructor_name=training.instructor_name,
        workplace_physician=training.workplace_physician,
        employer_representative=training.employer_representative,
        participant_count=len(participants),
        participants=participants,
        message="Belge doğrulandı." if valid else "Belge doğrulanamadı.",
    )
