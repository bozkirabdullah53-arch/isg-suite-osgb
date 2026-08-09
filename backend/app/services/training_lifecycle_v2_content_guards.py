"""Content guards for premium training lifecycle v2.

These wrappers prevent a post-cutover Work Start Training from accidentally
using the Basic İSG 20-question exam or Basic/NACE presentation. Historical
records and every other training kind delegate to the existing implementation.
"""
from __future__ import annotations

import sys
from functools import wraps

from fastapi import HTTPException

from app.services.training_lifecycle_v2 import applies_to_created_at, training_kind

_original_exam_builder = None
_original_presentation_readiness = None
_original_pilot_access = None


def _is_work_start(training) -> bool:
    return bool(
        applies_to_created_at(getattr(training, "created_at", None))
        and training_kind(
            getattr(training, "training_type", ""),
            getattr(training, "title", ""),
        )
        == "work_start"
    )


def install_training_lifecycle_v2_content_guards() -> dict[str, str]:
    global _original_exam_builder
    global _original_presentation_readiness
    global _original_pilot_access

    from app.api import training_presentation, trainings
    from app.services import training_exam_pdf, training_presentation_readiness

    status: dict[str, str] = {}

    current_exam = training_exam_pdf.build_exam_pdf
    if getattr(current_exam, "_premium_training_lifecycle_v2", False):
        status["work_start_exam"] = "already-active"
    else:
        _original_exam_builder = current_exam

        @wraps(current_exam)
        def premium_exam_builder(*, company_name: str, training, db, created_by_id: int) -> bytes:
            if _is_work_start(training):
                raise ValueError(
                    "İşe Başlama Eğitimi için 20 soruluk Temel İSG sınavı oluşturulmaz. "
                    "Bu eğitim, işe başlamadan önce yüz yüze ve uygulamalı olarak katılım/tutanak ile kayıt altına alınır."
                )
            return _original_exam_builder(
                company_name=company_name,
                training=training,
                db=db,
                created_by_id=created_by_id,
            )

        premium_exam_builder._premium_training_lifecycle_v2 = True
        training_exam_pdf.build_exam_pdf = premium_exam_builder
        trainings.build_exam_pdf = premium_exam_builder
        status["work_start_exam"] = "active"

    current_readiness = training_presentation_readiness.training_presentation_readiness
    if getattr(current_readiness, "_premium_training_lifecycle_v2", False):
        status["work_start_presentation_readiness"] = "already-active"
    else:
        _original_presentation_readiness = current_readiness

        @wraps(current_readiness)
        def premium_presentation_readiness(db, *, training):
            payload = dict(_original_presentation_readiness(db, training=training))
            if not _is_work_start(training):
                return payload

            check = {
                "code": "training_lifecycle_scope",
                "label": "Eğitim türü",
                "ok": False,
                "detail": (
                    "İşe Başlama Eğitimi, Temel İSG sunum/sınav akışından ayrıdır; "
                    "yanlış temel eğitim içeriği üretilmez."
                ),
            }
            checks = list(payload.get("checks") or [])
            if not any(item.get("code") == check["code"] for item in checks):
                checks.append(check)
            blockers = list(payload.get("blockers") or [])
            if not any(item.get("code") == check["code"] for item in blockers):
                blockers.append({"code": check["code"], "detail": check["detail"]})

            payload.update(
                {
                    "visible": False,
                    "generation_allowed": False,
                    "checks": checks,
                    "blockers": blockers,
                    "next_action": (
                        "İşe Başlama Eğitimi için Katılım/Tutanak akışını kullanın; "
                        "Temel İSG sunumu bu kayıt türünde üretilmez."
                    ),
                }
            )
            return payload

        premium_presentation_readiness._premium_training_lifecycle_v2 = True
        training_presentation_readiness.training_presentation_readiness = premium_presentation_readiness
        training_presentation.training_presentation_readiness = premium_presentation_readiness
        status["work_start_presentation_readiness"] = "active"

    current_access = training_presentation._ensure_pilot_access
    if getattr(current_access, "_premium_training_lifecycle_v2", False):
        status["work_start_presentation_generation"] = "already-active"
    else:
        _original_pilot_access = current_access

        @wraps(current_access)
        def premium_pilot_access(training) -> None:
            if _is_work_start(training):
                raise HTTPException(
                    409,
                    {
                        "code": "training_type_not_supported",
                        "message": (
                            "İşe Başlama Eğitimi için Temel İSG sunumu oluşturulmaz. "
                            "Katılım/Tutanak akışını kullanın."
                        ),
                        "core_training_unaffected": True,
                    },
                )
            return _original_pilot_access(training)

        premium_pilot_access._premium_training_lifecycle_v2 = True
        training_presentation._ensure_pilot_access = premium_pilot_access
        status["work_start_presentation_generation"] = "active"

    # Defensive update for any already imported direct references.
    api_training = sys.modules.get("app.api.trainings")
    if api_training is not None:
        api_training.build_exam_pdf = training_exam_pdf.build_exam_pdf

    return status
