"""Content guards for premium training lifecycle v2.

Post-cutover Work Start and Information Refresh trainings are record/tutanak
flows, not Basic İSG certificate, 20-question exam or NACE presentation flows.
These wrappers fail closed for only those two training kinds and delegate every
historical/Basic/special training to the existing implementation.
"""
from __future__ import annotations

import sys
from functools import wraps

from fastapi import HTTPException

from app.services.training_lifecycle_v2 import (
    WORK_SPECIFIC_HOURS,
    applies_to_created_at,
    training_kind,
)

_original_exam_builder = None
_original_certificate_builder = None
_original_curriculum = None
_original_presentation_readiness = None
_original_pilot_access = None


def _record_only_kind(training) -> str | None:
    if not applies_to_created_at(getattr(training, "created_at", None)):
        return None
    kind = training_kind(
        getattr(training, "training_type", ""),
        getattr(training, "title", ""),
    )
    return kind if kind in {"work_start", "information_refresh"} else None


def _label(kind: str) -> str:
    return "İşe Başlama Eğitimi" if kind == "work_start" else "Bilgi Yenileme Eğitimi"


def _information_refresh_curriculum(training, pdf_module) -> dict:
    hazard = str(getattr(training, "hazard_class", "") or "")
    hours = int(WORK_SPECIFIC_HOURS.get(hazard, 2))
    sector = pdf_module.sektor_kodu_cozumle(getattr(training, "sector", None))
    summary = pdf_module.katilim_formu_konu_ozeti(hazard, sector)
    topics = [
        "İşyerine ve yapılan işe özgü güncel tehlike ve riskler",
        "Risk değerlendirmesinde belirlenen korunma tedbirleri",
        "İş ekipmanı, çalışma yöntemi ve güvenli davranış kuralları",
        "Acil durum, tahliye ve bildirim düzeni",
        "İşe dönüş öncesi bilgi tazeleme ve saha uygulaması",
    ]
    return {
        "certificate_title": "BİLGİ YENİLEME İSG EĞİTİM KAYDI",
        "attendance_title": "BİLGİ YENİLEME İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİMİ",
        "profile_key": "premium_information_refresh",
        "is_special": True,
        "profile": None,
        "topics_header": "İŞE VE İŞYERİNE ÖZGÜ BİLGİ YENİLEME KONULARI",
        "purpose": (
            "Altı aydan fazla süreyle işten uzak kalan çalışanın işe başlamadan önce, "
            "işe ve işyerine özgü güncel riskler ve korunma tedbirleri hakkında bilgisini yenilemek."
        ),
        "legal_basis": (
            "Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında "
            "Yönetmeliğin bilgi yenileme eğitimi ve Ek-1 dördüncü konu başlığı hükümleri kapsamında düzenlenmiştir."
        ),
        "disclaimer": (
            "Bu kayıt Bilgi Yenileme Eğitimi tutanağıdır; düzenli Temel İSG tekrar eğitimi "
            "ve Temel İSG katılım belgesi yerine geçmez."
        ),
        "sol": [(1, "BİLGİ YENİLEME"), *[(0, f"- {item}") for item in topics[:3]]],
        "sag": [(1, "İŞYERİNE ÖZGÜ RİSKLER"), *[(0, f"- {item}") for item in topics[3:]]],
        "konu_ozeti": "; ".join(topics) + (f" | NACE/işe özgü: {summary}" if summary else ""),
        "duration_hours": hours,
        "duration_label": f"EN AZ {hours} DERS SAATİ",
        "duration_hint": f"En az {hours} ders saati · işe ve işyerine özgü riskler",
    }


def install_training_lifecycle_v2_content_guards() -> dict[str, str]:
    global _original_exam_builder
    global _original_certificate_builder
    global _original_curriculum
    global _original_presentation_readiness
    global _original_pilot_access

    from app.api import training_presentation, trainings
    from app.services import training_exam_pdf, training_pdfs, training_presentation_readiness

    status: dict[str, str] = {}

    current_curriculum = training_pdfs.resolve_training_curriculum
    if getattr(current_curriculum, "_premium_record_only_curriculum", False):
        status["record_only_curriculum"] = "already-active"
    else:
        _original_curriculum = current_curriculum

        @wraps(current_curriculum)
        def premium_curriculum(training):
            kind = _record_only_kind(training)
            if kind == "information_refresh":
                return _information_refresh_curriculum(training, training_pdfs)
            return _original_curriculum(training)

        premium_curriculum._premium_record_only_curriculum = True
        training_pdfs.resolve_training_curriculum = premium_curriculum
        status["record_only_curriculum"] = "active"

    current_exam = training_exam_pdf.build_exam_pdf
    if getattr(current_exam, "_premium_training_lifecycle_v2", False):
        status["record_only_exam"] = "already-active"
    else:
        _original_exam_builder = current_exam

        @wraps(current_exam)
        def premium_exam_builder(*, company_name: str, training, db, created_by_id: int) -> bytes:
            kind = _record_only_kind(training)
            if kind:
                raise ValueError(
                    f"{_label(kind)} için 20 soruluk Temel İSG sınavı oluşturulmaz. "
                    "Bu kayıt türünde katılım/tutanak akışını kullanın."
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
        status["record_only_exam"] = "active"

    current_certificate = training_pdfs.build_certificates_pdf
    if getattr(current_certificate, "_premium_record_only_certificate_guard", False):
        status["record_only_certificate"] = "already-active"
    else:
        _original_certificate_builder = current_certificate

        @wraps(current_certificate)
        def premium_certificate_builder(*, company_name: str, training, employees: dict) -> bytes:
            kind = _record_only_kind(training)
            if kind:
                raise ValueError(
                    f"{_label(kind)} için Temel İSG katılım belgesi oluşturulmaz. "
                    "Bu eğitim türünün Katılım/Tutanak PDF kaydını kullanın."
                )
            return _original_certificate_builder(
                company_name=company_name,
                training=training,
                employees=employees,
            )

        premium_certificate_builder._premium_record_only_certificate_guard = True
        training_pdfs.build_certificates_pdf = premium_certificate_builder
        trainings.build_certificates_pdf = premium_certificate_builder
        status["record_only_certificate"] = "active"

    current_readiness = training_presentation_readiness.training_presentation_readiness
    if getattr(current_readiness, "_premium_training_lifecycle_v2", False):
        status["record_only_presentation_readiness"] = "already-active"
    else:
        _original_presentation_readiness = current_readiness

        @wraps(current_readiness)
        def premium_presentation_readiness(db, *, training):
            payload = dict(_original_presentation_readiness(db, training=training))
            kind = _record_only_kind(training)
            if not kind:
                return payload

            label = _label(kind)
            check = {
                "code": "training_lifecycle_scope",
                "label": "Eğitim türü",
                "ok": False,
                "detail": (
                    f"{label}, Temel İSG sunum/sınav akışından ayrıdır; "
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
                        f"{label} için Katılım/Tutanak akışını kullanın; "
                        "Temel İSG sunumu bu kayıt türünde üretilmez."
                    ),
                }
            )
            return payload

        premium_presentation_readiness._premium_training_lifecycle_v2 = True
        training_presentation_readiness.training_presentation_readiness = premium_presentation_readiness
        training_presentation.training_presentation_readiness = premium_presentation_readiness
        status["record_only_presentation_readiness"] = "active"

    current_access = training_presentation._ensure_pilot_access
    if getattr(current_access, "_premium_training_lifecycle_v2", False):
        status["record_only_presentation_generation"] = "already-active"
    else:
        _original_pilot_access = current_access

        @wraps(current_access)
        def premium_pilot_access(training) -> None:
            kind = _record_only_kind(training)
            if kind:
                raise HTTPException(
                    409,
                    {
                        "code": "training_type_not_supported",
                        "message": (
                            f"{_label(kind)} için Temel İSG sunumu oluşturulmaz. "
                            "Katılım/Tutanak akışını kullanın."
                        ),
                        "core_training_unaffected": True,
                    },
                )
            return _original_pilot_access(training)

        premium_pilot_access._premium_training_lifecycle_v2 = True
        training_presentation._ensure_pilot_access = premium_pilot_access
        status["record_only_presentation_generation"] = "active"

    # Defensive updates for direct imports that were bound before these wrappers.
    api_training = sys.modules.get("app.api.trainings")
    if api_training is not None:
        api_training.build_exam_pdf = training_exam_pdf.build_exam_pdf
        api_training.build_certificates_pdf = training_pdfs.build_certificates_pdf

    return status