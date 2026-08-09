"""Safe completion for premium record-only training kinds."""
from __future__ import annotations

import sys
from datetime import date
from functools import wraps
from typing import Any

from app.models.entities import TrainingStatus
from app.services.training_lifecycle_v2 import applies_to_created_at, training_kind

_original_preflight = None
_original_finalize = None


def record_only_kind(training) -> str | None:
    if not applies_to_created_at(getattr(training, "created_at", None)):
        return None
    kind = training_kind(getattr(training, "training_type", ""), getattr(training, "title", ""))
    return kind if kind in {"work_start", "information_refresh"} else None


def _status_value(training) -> str:
    raw = getattr(training, "status", None)
    return str(getattr(raw, "value", raw) or "")


def record_only_preflight(training) -> dict[str, Any]:
    kind = record_only_kind(training)
    if kind is None:
        raise ValueError("Bu kayıt premium tutanak akışında değildir.")
    participants = list(getattr(training, "participants", None) or [])
    blockers: list[str] = []
    warnings: list[str] = []
    status = _status_value(training)
    end_date = getattr(training, "end_date", None) or getattr(training, "start_date", None)
    if not participants:
        blockers.append("Eğitimde katılımcı bulunmuyor.")
    if status == TrainingStatus.CANCELLED.value:
        blockers.append("İptal edilmiş eğitim sonuçlandırılamaz.")
    if end_date and end_date > date.today():
        blockers.append("Eğitim bitiş tarihi henüz gelmedi.")
    if not str(getattr(training, "instructor_name", "") or "").strip():
        blockers.append("Eğitici bilgisi eksik.")
    rows: list[dict[str, Any]] = []
    eligible_count = 0
    for participant in participants:
        attended = bool(getattr(participant, "attended", False))
        eligible = attended
        if eligible:
            eligible_count += 1
        rows.append({
            "participant_id": int(participant.id),
            "employee_id": int(participant.employee_id),
            "attended": attended,
            "score": None,
            "stored_successful": getattr(participant, "successful", None),
            "computed_successful": True if attended else False,
            "certificate_number": getattr(participant, "certificate_number", None),
            "eligible": eligible,
            "reasons": [] if attended else ["Eğitime katılım doğrulanmadı."],
        })
    finalized = status == TrainingStatus.COMPLETED.value and bool(getattr(training, "attendance_verified", False))
    ready_for_record = finalized and not blockers and eligible_count > 0
    if not finalized:
        blockers.append("Katılım sonuçları henüz kesinleştirilmedi.")
    if finalized and eligible_count == 0:
        blockers.append("Katıldığı doğrulanan çalışan bulunmuyor.")
    label = "İşe Başlama Eğitimi" if kind == "work_start" else "Bilgi Yenileme Eğitimi"
    warnings.append(f"{label}, Temel İSG katılım belgesi/sınavı yerine geçmez; ayrı tutanak kaydıdır.")
    return {
        "training_id": int(training.id),
        "strict_flag_enabled": True,
        "strict_applicable": True,
        "strict_enforced": True,
        "strict_after": None,
        "mode": f"premium_{kind}_attendance_record",
        "exam_required": False,
        "passing_score": None,
        "ready_for_certificates": False,
        "ready_for_record": ready_for_record,
        "document_mode": "attendance_record_only",
        "training_blockers": blockers,
        "warnings": warnings,
        "participant_total": len(rows),
        "eligible_count": eligible_count,
        "ineligible_count": len(rows) - eligible_count,
        "participants": rows,
    }


def finalize_record_only(training) -> dict[str, Any]:
    kind = record_only_kind(training)
    if kind is None:
        raise ValueError("Bu kayıt premium tutanak akışında değildir.")
    if _status_value(training) == TrainingStatus.CANCELLED.value:
        raise ValueError("İptal edilmiş eğitim tamamlanamaz.")
    end_date = getattr(training, "end_date", None) or getattr(training, "start_date", None)
    if end_date and end_date > date.today():
        raise ValueError("Eğitim bitiş tarihi gelmeden sonuçlar kesinleştirilemez.")
    participants = list(getattr(training, "participants", None) or [])
    if not participants:
        raise ValueError("Sonuçları kesinleştirmek için en az bir katılımcı gerekir.")
    attended_count = 0
    for participant in participants:
        attended = bool(getattr(participant, "attended", False))
        participant.score = None
        participant.successful = attended
        if attended:
            attended_count += 1
    if attended_count == 0:
        raise ValueError("Katıldığı doğrulanan en az bir çalışan olmadan eğitim sonuçlandırılamaz.")
    training.attendance_verified = True
    training.success_verified = True
    training.status = TrainingStatus.COMPLETED
    return record_only_preflight(training)


def install_training_lifecycle_v2_completion() -> dict[str, str]:
    global _original_preflight, _original_finalize
    from app.services import training_completion
    status: dict[str, str] = {}
    current_preflight = training_completion.completion_preflight
    if getattr(current_preflight, "_premium_record_only_completion", False):
        status["preflight"] = "already-active"
    else:
        _original_preflight = current_preflight
        @wraps(current_preflight)
        def premium_preflight(db, training):
            if record_only_kind(training):
                return record_only_preflight(training)
            return _original_preflight(db, training)
        premium_preflight._premium_record_only_completion = True
        training_completion.completion_preflight = premium_preflight
        status["preflight"] = "active"
    current_finalize = training_completion.finalize_training_results
    if getattr(current_finalize, "_premium_record_only_completion", False):
        status["finalize"] = "already-active"
    else:
        _original_finalize = current_finalize
        @wraps(current_finalize)
        def premium_finalize(db, training):
            if record_only_kind(training):
                result = finalize_record_only(training)
                db.flush()
                return result
            return _original_finalize(db, training)
        premium_finalize._premium_record_only_completion = True
        training_completion.finalize_training_results = premium_finalize
        status["finalize"] = "active"
    api_completion = sys.modules.get("app.api.training_completion")
    if api_completion is not None:
        api_completion.completion_preflight = training_completion.completion_preflight
        api_completion.finalize_training_results = training_completion.finalize_training_results
    return status
