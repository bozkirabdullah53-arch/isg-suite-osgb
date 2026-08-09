"""Training result finalization and certificate eligibility guard.

Strict enforcement applies only to trainings with a persisted/verified NACE
snapshot, when ``TRAINING_COMPLETION_STRICT=true``, and optionally only after the
ISO timestamp in ``TRAINING_COMPLETION_STRICT_AFTER``. This cutover preserves all
pre-existing training and certificate workflows. No historical PDF or exam
snapshot is modified.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.models.entities import TrainingParticipant, TrainingSession, TrainingStatus
from app.models.training_nace import TrainingNaceSnapshot
from app.services.special_training_profiles import resolve_special_profile_key

STRICT_ENV = "TRAINING_COMPLETION_STRICT"
STRICT_AFTER_ENV = "TRAINING_COMPLETION_STRICT_AFTER"

_original_certificate_builder = None


def completion_strict_active() -> bool:
    value = str(os.getenv(STRICT_ENV, "false") or "").strip().casefold()
    return value in {"1", "true", "yes", "on"}


def _strict_after() -> datetime | None:
    raw = str(os.getenv(STRICT_AFTER_ENV, "") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def verified_snapshot(db: Session, training: TrainingSession) -> TrainingNaceSnapshot | None:
    if not getattr(training, "id", None):
        return None
    return db.scalar(
        select(TrainingNaceSnapshot).where(
            TrainingNaceSnapshot.training_id == training.id,
            TrainingNaceSnapshot.classification_status == "verified",
        )
    )


def completion_strict_applies(
    db: Session, training: TrainingSession
) -> tuple[bool, TrainingNaceSnapshot | None]:
    snapshot = verified_snapshot(db, training)
    if not completion_strict_active() or snapshot is None:
        return False, snapshot
    cutover = _strict_after()
    if cutover is not None:
        created_at = getattr(snapshot, "created_at", None)
        if created_at is None or created_at < cutover:
            return False, snapshot
    return True, snapshot


def exam_required(training: TrainingSession) -> bool:
    # Yüksekte çalışma özel modülü 20 soruluk sınav içerir; eski kayıtların
    # değerlendirme alanı "Katılım esası" olsa bile sınav akışı korunur.
    if resolve_special_profile_key(training) == "yuksekte_calisma":
        return True
    method = str(getattr(training, "evaluation_method", "") or "").strip().casefold()
    if any(token in method for token in ("sınav", "sinav", "test", "quiz", "yazılı", "yazili")):
        return True
    if any(
        token in method
        for token in ("katılım", "katilim", "uygulama", "gözlem", "gozlem", "sözlü", "sozlu")
    ):
        return False
    return True


def _status_value(training: TrainingSession) -> str:
    value = getattr(training, "status", None)
    return str(getattr(value, "value", value) or "")


def _participant_check(
    participant: TrainingParticipant,
    *,
    needs_exam: bool,
    passing_score: int | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    attended = bool(participant.attended)
    score = participant.score
    computed_success: bool | None = None
    if not attended:
        reasons.append("Eğitime katılım doğrulanmadı.")
    if needs_exam and attended:
        if passing_score is None:
            reasons.append("Eğitimin geçme puanı tanımlı değil.")
        if score is None:
            reasons.append("Sınav puanı girilmedi.")
        elif not 0 <= int(score) <= 100:
            reasons.append("Sınav puanı 0–100 aralığında değil.")
        elif passing_score is not None:
            computed_success = int(score) >= int(passing_score)
            if not computed_success:
                reasons.append(f"Sınav puanı geçme puanının altında ({score}/{passing_score}).")
            if participant.successful is not None and bool(participant.successful) != computed_success:
                reasons.append("Kaydedilmiş başarı durumu sınav puanıyla tutarsız.")
    elif attended:
        computed_success = True

    eligible = attended and not reasons and (not needs_exam or computed_success is True)
    return {
        "participant_id": participant.id,
        "employee_id": participant.employee_id,
        "attended": attended,
        "score": score,
        "stored_successful": participant.successful,
        "computed_successful": computed_success,
        "certificate_number": participant.certificate_number,
        "eligible": eligible,
        "reasons": reasons,
    }


def _legacy_preflight(
    training: TrainingSession,
    participants: list[TrainingParticipant],
    *,
    snapshot: TrainingNaceSnapshot | None,
) -> dict[str, Any]:
    before_cutover = snapshot is not None
    warning = (
        "Eğitim strict geçiş tarihinden önce oluşturulduğu için mevcut belge davranışı korunur."
        if before_cutover
        else "Persisted/verified NACE snapshot bulunmadığı için legacy davranış korunur."
    )
    return {
        "training_id": training.id,
        "strict_flag_enabled": completion_strict_active(),
        "strict_applicable": snapshot is not None,
        "strict_enforced": False,
        "strict_after": os.getenv(STRICT_AFTER_ENV) or None,
        "mode": "verified_pre_cutover_compatibility" if before_cutover else "legacy_compatibility",
        "ready_for_certificates": bool(participants),
        "training_blockers": [],
        "warnings": [warning],
        "participant_total": len(participants),
        "eligible_count": len(participants),
        "ineligible_count": 0,
        "participants": [
            {
                "participant_id": p.id,
                "employee_id": p.employee_id,
                "attended": p.attended,
                "score": p.score,
                "stored_successful": p.successful,
                "computed_successful": p.successful,
                "certificate_number": p.certificate_number,
                "eligible": True,
                "reasons": [],
            }
            for p in participants
        ],
    }


def completion_preflight(db: Session, training: TrainingSession) -> dict[str, Any]:
    enforced, snapshot = completion_strict_applies(db, training)
    participants = list(training.participants or [])
    needs_exam = exam_required(training)
    passing = training.passing_score

    if not enforced:
        return _legacy_preflight(training, participants, snapshot=snapshot)

    blockers: list[str] = []
    warnings: list[str] = []
    if not participants:
        blockers.append("Eğitimde katılımcı bulunmuyor.")
    if _status_value(training) == TrainingStatus.CANCELLED.value:
        blockers.append("İptal edilmiş eğitim için belge üretilemez.")
    elif _status_value(training) != TrainingStatus.COMPLETED.value:
        blockers.append("Eğitim tamamlandı durumuna alınmamış.")
    end_date = training.end_date or training.start_date
    if end_date and end_date > date.today():
        blockers.append("Eğitim bitiş tarihi henüz gelmedi.")
    if not bool(training.attendance_verified):
        blockers.append("Katılım kayıtları yetkili kullanıcı tarafından doğrulanmadı.")
    if needs_exam:
        if passing is None:
            blockers.append("Sınav değerlendirmesi için geçme puanı tanımlanmadı.")
        if not bool(training.success_verified):
            blockers.append("Sınav sonuçları yetkili kullanıcı tarafından doğrulanmadı.")
    if not str(training.instructor_name or "").strip():
        blockers.append("Eğitici bilgisi eksik.")
    if not str(training.workplace_physician or "").strip():
        warnings.append("İşyeri hekimi adı belge imza alanında boş kalacak.")
    if not str(training.employer_representative or "").strip():
        warnings.append("İşveren/işveren vekili adı belge imza alanında boş kalacak.")

    rows = [
        _participant_check(p, needs_exam=needs_exam, passing_score=passing)
        for p in participants
    ]
    eligible_count = sum(int(row["eligible"]) for row in rows)
    ready = not blockers and eligible_count > 0
    return {
        "training_id": training.id,
        "strict_flag_enabled": completion_strict_active(),
        "strict_applicable": True,
        "strict_enforced": True,
        "strict_after": os.getenv(STRICT_AFTER_ENV) or None,
        "mode": "verified_nace_completion",
        "nace": snapshot.nace_code,
        "catalog_key": snapshot.catalog_key,
        "exam_required": needs_exam,
        "passing_score": passing,
        "ready_for_certificates": ready,
        "training_blockers": blockers,
        "warnings": warnings,
        "participant_total": len(rows),
        "eligible_count": eligible_count,
        "ineligible_count": len(rows) - eligible_count,
        "participants": rows,
    }


def finalize_training_results(db: Session, training: TrainingSession) -> dict[str, Any]:
    """Validate all result rows, derive success, and close one verified training."""
    if verified_snapshot(db, training) is None:
        raise ValueError("Yalnız persisted/verified NACE eğitimleri bu güvenli akışla tamamlanabilir.")
    if _status_value(training) == TrainingStatus.CANCELLED.value:
        raise ValueError("İptal edilmiş eğitim tamamlanamaz.")
    end_date = training.end_date or training.start_date
    if end_date and end_date > date.today():
        raise ValueError("Eğitim bitiş tarihi gelmeden sonuçlar kesinleştirilemez.")
    participants = list(training.participants or [])
    if not participants:
        raise ValueError("Sonuçları kesinleştirmek için en az bir katılımcı gerekir.")

    needs_exam = exam_required(training)
    passing = training.passing_score
    if needs_exam and passing is None:
        raise ValueError("Sınavlı eğitimde geçme puanı tanımlanmalıdır.")

    for participant in participants:
        if not participant.attended:
            participant.score = None
            participant.successful = False
            continue
        if needs_exam:
            if participant.score is None:
                raise ValueError(
                    f"Katılan personelin sınav puanı eksik (katılımcı #{participant.id})."
                )
            if not 0 <= int(participant.score) <= 100:
                raise ValueError(
                    f"Sınav puanı 0–100 aralığında olmalıdır (katılımcı #{participant.id})."
                )
            participant.successful = int(participant.score) >= int(passing)
        else:
            participant.successful = True

    training.attendance_verified = True
    training.success_verified = True if needs_exam else bool(training.success_verified)
    training.status = TrainingStatus.COMPLETED
    db.flush()
    return completion_preflight(db, training)


def eligible_participants(db: Session, training: TrainingSession) -> list[TrainingParticipant]:
    preflight = completion_preflight(db, training)
    eligible_ids = {
        int(row["participant_id"])
        for row in preflight["participants"]
        if row["eligible"]
    }
    return [p for p in training.participants if p.id in eligible_ids]


class _TrainingProxy:
    def __init__(self, training: TrainingSession, participants: list[TrainingParticipant]):
        self._training = training
        self.participants = participants

    def __getattr__(self, name: str):
        return getattr(self._training, name)


def _compliant_certificate_pdf(
    pdf_module,
    *,
    company_name: str,
    training: TrainingSession,
    employees: dict,
    participants: list[TrainingParticipant],
) -> bytes:
    """Use existing renderer but stable stored certificate numbers and filtered people."""
    pdf_module._ensure_fonts()
    proxy = _TrainingProxy(training, participants)
    buf = BytesIO()
    page = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page)
    w, h = page
    today_text = datetime.now().strftime("%d.%m.%Y")
    training_date = pdf_module._fmt_date_range(proxy)
    rule = pdf_module.tehlike_kurali(proxy.hazard_class)
    sector = pdf_module.sektor_kodu_cozumle(proxy.sector)
    curriculum = pdf_module.resolve_training_curriculum(proxy)
    if curriculum.get("is_special") and curriculum.get("sol") is not None:
        left, right = curriculum["sol"], curriculum["sag"]
    else:
        left, right, _, _ = pdf_module.egitim_konularini_hazirla(
            proxy.hazard_class, sector
        )

    for participant in participants:
        employee = employees.get(participant.employee_id)
        certificate_no = str(participant.certificate_number or "").strip()
        if not certificate_no:
            certificate_no = f"EGT-{training.id:06d}-{participant.employee_id:06d}"
        pdf_module._draw_certificate_page(
            c,
            w,
            h,
            company_name=company_name,
            training=proxy,
            employee=employee,
            belge_no=certificate_no,
            bugun=today_text,
            egitim_tarihi=training_date,
            kural=rule,
            sektor=sector,
            sol=left,
            sag=right,
            curriculum=curriculum,
        )
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def install_training_completion_guard() -> dict[str, str]:
    """Patch certificate generation at its imported call sites, idempotently."""
    global _original_certificate_builder

    from app.services import training_pdfs

    current = training_pdfs.build_certificates_pdf
    if getattr(current, "_verified_completion_guard_active", False):
        return {
            "certificate_guard": "already-active",
            "strict_flag": str(completion_strict_active()).lower(),
        }
    _original_certificate_builder = current

    def guarded_builder(*, company_name: str, training, employees: dict) -> bytes:
        db = object_session(training)
        applies, _snapshot = completion_strict_applies(db, training) if db is not None else (False, None)
        if not applies:
            return _original_certificate_builder(
                company_name=company_name,
                training=training,
                employees=employees,
            )
        preflight = completion_preflight(db, training)
        if not preflight["ready_for_certificates"]:
            details = "; ".join(preflight["training_blockers"])
            if preflight["eligible_count"] == 0:
                details = (details + "; " if details else "") + "Belge almaya hak kazanan katılımcı yok."
            raise ValueError(f"Katılım belgesi üretilemez: {details}")
        selected = eligible_participants(db, training)
        return _compliant_certificate_pdf(
            training_pdfs,
            company_name=company_name,
            training=training,
            employees=employees,
            participants=selected,
        )

    guarded_builder._verified_completion_guard_active = True
    training_pdfs.build_certificates_pdf = guarded_builder
    for module_name in ("app.api.trainings",):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "build_certificates_pdf"):
            setattr(module, "build_certificates_pdf", guarded_builder)
    return {
        "certificate_guard": "active",
        "strict_flag": str(completion_strict_active()).lower(),
        "strict_after": os.getenv(STRICT_AFTER_ENV) or "",
    }
