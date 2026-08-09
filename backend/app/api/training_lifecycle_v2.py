"""Read-only premium training lifecycle endpoints.

No endpoint in this module mutates historical training data. Existing result and
finalization endpoints remain the only write path for attendance/score/finalize.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import TrainingSession, TrainingStatus, User
from app.services import training_completion
from app.services.training_lifecycle_v2 import (
    applies_to_created_at,
    policy_for,
    public_policy,
)

router = APIRouter(prefix="/trainings", tags=["Eğitim Premium Yaşam Döngüsü"])


@router.get("/premium-policy")
def premium_training_policy(user: User = Depends(get_current_user)):
    # Authenticated because this policy drives the private Training UI.
    return public_policy()


@router.get("/{training_id}/premium-lifecycle")
def premium_training_lifecycle(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    training = db.get(TrainingSession, training_id)
    if training is None:
        raise HTTPException(404, "Eğitim kaydı bulunamadı.")
    ensure_company_access(db, user, training.company_id)

    policy = policy_for(
        training_type=training.training_type,
        title=training.title,
        hazard_class=training.hazard_class,
    )
    post_cutover = applies_to_created_at(training.created_at)
    status = getattr(training.status, "value", training.status)

    if not post_cutover:
        return {
            "training_id": training.id,
            "premium_enforced": False,
            "stage": "legacy",
            "stage_label": "Mevcut kayıt akışı korunuyor",
            "next_action": "Tarihsel kayıt mevcut davranışıyla kullanılmaya devam eder.",
            "policy": policy,
        }

    if str(status) == TrainingStatus.CANCELLED.value:
        return {
            "training_id": training.id,
            "premium_enforced": True,
            "stage": "cancelled",
            "stage_label": "İptal edildi",
            "next_action": "İptal edilen eğitim için çıktı üretilemez.",
            "policy": policy,
        }

    preflight = training_completion.completion_preflight(db, training)
    participants = list(training.participants or [])
    has_result_data = any(
        bool(participant.attended)
        or participant.score is not None
        or participant.successful is not None
        for participant in participants
    )
    end_date = training.end_date or training.start_date
    record_only = policy.get("kind") in {"work_start", "information_refresh"}

    if record_only and str(status) == TrainingStatus.COMPLETED.value and preflight.get("ready_for_record"):
        stage = "record_ready"
        label = "Tutanak kaydı hazır"
        next_action = "Katılım/Tutanak PDF kaydını oluşturabilir ve eğitim dosyasında saklayabilirsiniz."
    elif (not record_only) and str(status) == TrainingStatus.COMPLETED.value and preflight.get("ready_for_certificates"):
        stage = "document_ready"
        label = "Belgeye hazır"
        next_action = "Katılım belgesi, katılım/imza tutanağı ve diğer çıktıları ayrı ayrı oluşturabilirsiniz."
    elif has_result_data:
        stage = "results_pending"
        label = "Sonuçlar kesinleştirilecek"
        next_action = (
            "Gerçek katılımı kontrol edin ve Sonuçları Kesinleştir adımını kullanın."
            if record_only
            else "Katılım ve sınav sonuçlarını kontrol edin, ardından Sonuçları Kesinleştir adımını kullanın."
        )
    elif end_date and end_date <= date.today():
        stage = "attendance_pending"
        label = "Katılım / sonuç bekliyor"
        next_action = (
            "Eğitime gerçekten katılan çalışanları işaretleyin."
            if record_only
            else "Eğitime katılanları ve varsa sınav puanlarını girin."
        )
    else:
        stage = "planned"
        label = "Planlandı"
        next_action = "Eğitim günü geldiğinde katılımı kaydedin; planlama aşamasında başarı doğrulanmaz."

    return {
        "training_id": training.id,
        "premium_enforced": True,
        "stage": stage,
        "stage_label": label,
        "next_action": next_action,
        "policy": policy,
        "completion": {
            "ready_for_certificates": bool(preflight.get("ready_for_certificates")),
            "ready_for_record": bool(preflight.get("ready_for_record")),
            "document_mode": preflight.get("document_mode"),
            "eligible_count": int(preflight.get("eligible_count") or 0),
            "ineligible_count": int(preflight.get("ineligible_count") or 0),
            "blockers": list(preflight.get("training_blockers") or []),
            "warnings": list(preflight.get("warnings") or []),
        },
    }