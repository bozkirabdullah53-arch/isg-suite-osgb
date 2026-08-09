"""Additive 2026 training lifecycle and duration policy.

The service is deliberately data-migration free. Existing persisted training,
exam, presentation, PDF, certificate and attendance records are never rewritten.
New behavior is gated by environment flags and an optional cutover timestamp.

Implementation strategy:
- patch only the training-create duration resolver while the flag is active;
- rewrite only NEW training-create JSON at the HTTP boundary so planning never
  pre-confirms attendance/success;
- exclude post-cutover work-start/information-refresh records from the basic
  renewal calculation;
- reuse the existing strict completion guard for post-cutover verified-NACE
  records even if a legacy global strict flag is not configured;
- make work-start attendance output an explicit work-start record and prevent a
  misleading Basic İSG certificate from being generated;
- leave every historical record and legacy path unchanged when the flag is off.

The middleware intentionally does NOT authorize, complete or mutate existing
training rows. Route-level authentication/authorization remains untouched.
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

PREMIUM_ENV = "TRAINING_PREMIUM_LIFECYCLE_V2_ENABLED"
PREMIUM_FORCE_OFF_ENV = "TRAINING_PREMIUM_LIFECYCLE_V2_FORCE_OFF"
PREMIUM_AFTER_ENV = "TRAINING_PREMIUM_LIFECYCLE_V2_AFTER"
POLICY_VERSION = "training-premium-lifecycle-v2"
SOURCE_CHECK_DATE = "2026-08-09"
OFFICIAL_SOURCE_URL = (
    "https://www.csgb.gov.tr/tr/sikca-sorulan-sorular/"
    "is-sagligi-ve-guvenligi-genel-mudurlugu/"
)

INITIAL_BASIC_HOURS = {
    "Az Tehlikeli": 8,
    "Tehlikeli": 12,
    "Çok Tehlikeli": 16,
}
REPEAT_BASIC_HOURS = {
    "Az Tehlikeli": 8,
    "Tehlikeli": 8,
    "Çok Tehlikeli": 8,
}
WORK_SPECIFIC_HOURS = {
    "Az Tehlikeli": 2,
    "Tehlikeli": 3,
    "Çok Tehlikeli": 4,
}
RENEWAL_YEARS = {
    "Az Tehlikeli": 3,
    "Tehlikeli": 2,
    "Çok Tehlikeli": 1,
}

_START_TOKENS = ("ise baslama",)
_REPEAT_TOKENS = ("tekrar", "yenileme egitimi")
_INFORMATION_REFRESH_TOKENS = ("bilgi yenileme", "bilgi tazeleme")

_original_resolve_training_hours = None
_original_basic_training_predicate = None
_original_completion_strict_applies = None
_original_compliant_certificate_pdf = None
_original_pdf_titles = None
_original_pdf_curriculum = None


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def premium_lifecycle_active() -> bool:
    return _truthy(os.getenv(PREMIUM_ENV)) and not _truthy(os.getenv(PREMIUM_FORCE_OFF_ENV))


def _cutover() -> datetime | None:
    raw = str(os.getenv(PREMIUM_AFTER_ENV, "") or "").strip()
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def applies_to_created_at(created_at: datetime | None) -> bool:
    if not premium_lifecycle_active():
        return False
    cutover = _cutover()
    if cutover is None:
        return True
    if created_at is None:
        return False
    value = created_at
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value >= cutover


def applies_to_new_request(now: datetime | None = None) -> bool:
    value = now or datetime.now(timezone.utc).replace(tzinfo=None)
    return applies_to_created_at(value)


def _fold(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").casefold())
    without_marks = "".join(char for char in raw if not unicodedata.combining(char))
    text = " ".join(without_marks.strip().split())
    return text.translate(
        str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u"})
    )


def training_kind(training_type: object, title: object = "") -> str:
    haystack = f"{_fold(training_type)} {_fold(title)}"
    if any(token in haystack for token in _START_TOKENS):
        return "work_start"
    if any(token in haystack for token in _INFORMATION_REFRESH_TOKENS):
        return "information_refresh"
    if any(token in haystack for token in _REPEAT_TOKENS):
        return "repeat_basic"
    return "initial_basic"


def duration_hours(*, training_type: object, title: object, hazard_class: str) -> int:
    kind = training_kind(training_type, title)
    if kind == "work_start":
        return 2
    if kind == "repeat_basic":
        return int(REPEAT_BASIC_HOURS.get(hazard_class, 8))
    if kind == "information_refresh":
        return int(WORK_SPECIFIC_HOURS.get(hazard_class, 2))
    return int(INITIAL_BASIC_HOURS.get(hazard_class, 8))


def delivery_policy(*, training_type: object, title: object, hazard_class: str) -> dict[str, Any]:
    kind = training_kind(training_type, title)
    if kind == "work_start":
        return {
            "required": "Yüz yüze",
            "allowed": ["Yüz yüze"],
            "reason": "İşe başlama eğitimi tüm tehlike sınıflarında yüz yüze verilir.",
        }
    if kind == "information_refresh" and hazard_class in {"Tehlikeli", "Çok Tehlikeli"}:
        return {
            "required": "Yüz yüze",
            "allowed": ["Yüz yüze"],
            "reason": "Tehlikeli ve Çok Tehlikeli işyerlerinde işe özgü bilgi yenileme eğitimi yüz yüze verilir.",
        }
    return {
        "required": None,
        "allowed": ["Yüz yüze", "Uzaktan", "Karma"],
        "reason": "Yöntem, eğitim türü ve işe özgü bölümün tehlike sınıfı kuralına göre seçilir.",
    }


def policy_for(*, training_type: object, title: object, hazard_class: str) -> dict[str, Any]:
    return {
        "version": POLICY_VERSION,
        "kind": training_kind(training_type, title),
        "duration_hours": duration_hours(
            training_type=training_type,
            title=title,
            hazard_class=hazard_class,
        ),
        "work_specific_hours": int(WORK_SPECIFIC_HOURS.get(hazard_class, 2)),
        "renewal_years": RENEWAL_YEARS.get(hazard_class),
        "lesson_definition": "1 ders saati = 45 dakika ders + 15 dakika ara dinlenmesi",
        "delivery": delivery_policy(
            training_type=training_type,
            title=title,
            hazard_class=hazard_class,
        ),
    }


def public_policy() -> dict[str, Any]:
    return {
        "enabled": premium_lifecycle_active(),
        "force_off": _truthy(os.getenv(PREMIUM_FORCE_OFF_ENV)),
        "cutover": os.getenv(PREMIUM_AFTER_ENV) or None,
        "version": POLICY_VERSION,
        "checked_at": SOURCE_CHECK_DATE,
        "official_source": {
            "title": "ÇSGB / İSGGM Sıkça Sorulan Sorular – Çalışanların İSG Eğitimleri",
            "url": OFFICIAL_SOURCE_URL,
            "checked_at": SOURCE_CHECK_DATE,
        },
        "rules": {
            "work_start": {"label": "İşe Başlama Eğitimi", "minimum_hours": 2, "delivery": "Yüz yüze"},
            "initial_basic": {"label": "İlk Temel İSG Eğitimi", "hours": dict(INITIAL_BASIC_HOURS)},
            "repeat_basic": {"label": "Tekrar Temel İSG Eğitimi", "hours": dict(REPEAT_BASIC_HOURS)},
            "information_refresh": {"label": "Bilgi Yenileme Eğitimi", "work_specific_hours": dict(WORK_SPECIFIC_HOURS)},
            "work_specific": {
                "label": "4. konu başlığı / işe özgü riskler",
                "hours": dict(WORK_SPECIFIC_HOURS),
                "hazardous_delivery": "Tehlikeli ve Çok Tehlikeli: yüz yüze",
            },
            "renewal_years": dict(RENEWAL_YEARS),
            "lesson_definition": "45 dakika ders + 15 dakika ara dinlenmesi",
        },
        "safety": {
            "historical_records_rewritten": False,
            "migration_required": False,
            "rollback": f"{PREMIUM_FORCE_OFF_ENV}=true",
        },
    }


def _work_start_curriculum(training, pdf_module) -> dict[str, Any]:
    sector = pdf_module.sektor_kodu_cozumle(getattr(training, "sector", None))
    work_specific = pdf_module.katilim_formu_konu_ozeti(getattr(training, "hazard_class", ""), sector)
    generic = [
        "Yapacağı iş, çalışma ortamı ve işyerine özgü tehlike/riskler",
        "Kullanılacak iş ekipmanlarının güvenli kullanımı ve acil durdurma sistemleri",
        "Acil çıkış yolları, acil durum prosedürleri ve toplanma düzeni",
        "Risk değerlendirmesinde belirlenen işe ve işyerine özgü korunma tedbirleri",
        "Güvenli işe başlama davranışları ve uygulamalı saha bilgilendirmesi",
    ]
    return {
        "certificate_title": "İŞE BAŞLAMA İSG EĞİTİM KAYDI",
        "attendance_title": "İŞE BAŞLAMA İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİMİ",
        "profile_key": "premium_work_start",
        "is_special": True,
        "profile": None,
        "topics_header": "İŞE BAŞLAMA EĞİTİM KONULARI",
        "purpose": "Çalışanın fiilen işe başlamadan önce yapacağı işi, çalışma ortamını, kullanacağı iş ekipmanını ve işyerine özgü iş sağlığı ve güvenliği tedbirlerini güvenli şekilde tanıması.",
        "legal_basis": "6331 sayılı İş Sağlığı ve Güvenliği Kanunu ve Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik kapsamında işe başlamadan önce yüz yüze ve uygulamalı olarak düzenlenmiştir.",
        "disclaimer": "Bu kayıt Temel İSG Eğitimi yerine geçmez.",
        "sol": [(1, "İŞE BAŞLAMA"), *[(0, f"- {item}") for item in generic[:3]]],
        "sag": [(1, "İŞYERİNE ÖZGÜ RİSKLER"), *[(0, f"- {item}") for item in generic[3:]]],
        "konu_ozeti": "; ".join(generic) + (f" | NACE/işe özgü: {work_specific}" if work_specific else ""),
        "duration_hours": 2,
        "duration_label": "EN AZ 2 SAAT",
        "duration_hint": "En az 2 saat · yüz yüze ve uygulamalı",
    }


def install_training_lifecycle_v2() -> dict[str, str]:
    global _original_resolve_training_hours, _original_basic_training_predicate
    global _original_completion_strict_applies, _original_compliant_certificate_pdf
    global _original_pdf_titles, _original_pdf_curriculum

    from app.api import trainings
    from app.schemas import training as training_schema
    from app.services import training_completion, training_pdfs
    from app.services.special_training_profiles import resolve_special_duration_hours

    status: dict[str, str] = {}
    current = training_schema.resolve_training_hours
    if getattr(current, "_premium_training_lifecycle_v2", False):
        status["duration_policy"] = "already-active"
    else:
        _original_resolve_training_hours = current
        def premium_resolve_training_hours(*, training_type: str, title: str, notes: str | None, hazard_class: str) -> int:
            if not applies_to_new_request():
                return int(_original_resolve_training_hours(training_type=training_type, title=title, notes=notes, hazard_class=hazard_class))
            special = resolve_special_duration_hours(SimpleNamespace(training_type=training_type, title=title, notes=notes or ""))
            if special:
                return int(special)
            return duration_hours(training_type=training_type, title=title, hazard_class=hazard_class)
        premium_resolve_training_hours._premium_training_lifecycle_v2 = True
        training_schema.resolve_training_hours = premium_resolve_training_hours
        trainings.resolve_training_hours = premium_resolve_training_hours
        status["duration_policy"] = "active"

    current_basic = trainings._is_basic_training
    if getattr(current_basic, "_premium_training_lifecycle_v2", False):
        status["renewal_scope"] = "already-active"
    else:
        _original_basic_training_predicate = current_basic
        def premium_basic_training_predicate(row) -> bool:
            if applies_to_created_at(getattr(row, "created_at", None)):
                kind = training_kind(getattr(row, "training_type", ""), getattr(row, "title", ""))
                if kind in {"work_start", "information_refresh"}:
                    return False
            return bool(_original_basic_training_predicate(row))
        premium_basic_training_predicate._premium_training_lifecycle_v2 = True
        trainings._is_basic_training = premium_basic_training_predicate
        status["renewal_scope"] = "active"

    current_applies = training_completion.completion_strict_applies
    if getattr(current_applies, "_premium_training_lifecycle_v2", False):
        status["completion_strict"] = "already-active"
    else:
        _original_completion_strict_applies = current_applies
        def premium_completion_strict_applies(db, training):
            if db is not None and applies_to_created_at(getattr(training, "created_at", None)):
                snapshot = training_completion.verified_snapshot(db, training)
                if snapshot is not None:
                    return True, snapshot
            return _original_completion_strict_applies(db, training)
        premium_completion_strict_applies._premium_training_lifecycle_v2 = True
        training_completion.completion_strict_applies = premium_completion_strict_applies
        api_completion = sys.modules.get("app.api.training_completion")
        if api_completion is not None and hasattr(api_completion, "completion_strict_applies"):
            api_completion.completion_strict_applies = premium_completion_strict_applies
        status["completion_strict"] = "active"

    current_titles = training_pdfs.resolve_training_document_titles
    if getattr(current_titles, "_premium_training_lifecycle_v2", False):
        status["work_start_titles"] = "already-active"
    else:
        _original_pdf_titles = current_titles
        def premium_pdf_titles(training):
            if applies_to_created_at(getattr(training, "created_at", None)) and training_kind(getattr(training, "training_type", ""), getattr(training, "title", "")) == "work_start":
                return {"certificate_title": "İŞE BAŞLAMA İSG EĞİTİM KAYDI", "attendance_title": "İŞE BAŞLAMA İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİMİ", "profile_key": "premium_work_start"}
            return _original_pdf_titles(training)
        premium_pdf_titles._premium_training_lifecycle_v2 = True
        training_pdfs.resolve_training_document_titles = premium_pdf_titles
        status["work_start_titles"] = "active"

    current_curriculum = training_pdfs.resolve_training_curriculum
    if getattr(current_curriculum, "_premium_training_lifecycle_v2", False):
        status["work_start_curriculum"] = "already-active"
    else:
        _original_pdf_curriculum = current_curriculum
        def premium_pdf_curriculum(training):
            if applies_to_created_at(getattr(training, "created_at", None)) and training_kind(getattr(training, "training_type", ""), getattr(training, "title", "")) == "work_start":
                return _work_start_curriculum(training, training_pdfs)
            return _original_pdf_curriculum(training)
        premium_pdf_curriculum._premium_training_lifecycle_v2 = True
        training_pdfs.resolve_training_curriculum = premium_pdf_curriculum
        status["work_start_curriculum"] = "active"

    current_compliant = training_completion._compliant_certificate_pdf
    if getattr(current_compliant, "_premium_training_lifecycle_v2", False):
        status["work_start_certificate_guard"] = "already-active"
    else:
        _original_compliant_certificate_pdf = current_compliant
        def premium_compliant_certificate_pdf(pdf_module, *, company_name: str, training, employees: dict, participants: list) -> bytes:
            if applies_to_created_at(getattr(training, "created_at", None)) and training_kind(getattr(training, "training_type", ""), getattr(training, "title", "")) == "work_start":
                raise ValueError("İşe Başlama Eğitimi için Temel İSG katılım belgesi oluşturulmaz. İşe Başlama Eğitimi Tutanağı / Katılım PDF kaydını kullanın.")
            return _original_compliant_certificate_pdf(pdf_module, company_name=company_name, training=training, employees=employees, participants=participants)
        premium_compliant_certificate_pdf._premium_training_lifecycle_v2 = True
        training_completion._compliant_certificate_pdf = premium_compliant_certificate_pdf
        status["work_start_certificate_guard"] = "active"
    return status


class PremiumTrainingLifecycleMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not premium_lifecycle_active():
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method") or "").upper()
        path = str(scope.get("path") or "")
        if method != "POST" or path.rstrip("/") != "/api/v1/trainings" or not applies_to_new_request():
            await self.app(scope, receive, send)
            return
        body = await self._read_body(receive)
        rewritten = self._rewrite_new_training(body)
        await self.app(scope, self._body_receiver(rewritten), send)

    @staticmethod
    async def _read_body(receive) -> bytes:
        chunks: list[bytes] = []
        more = True
        while more:
            message = await receive()
            if message.get("type") != "http.request":
                continue
            chunks.append(message.get("body", b""))
            more = bool(message.get("more_body"))
        return b"".join(chunks)

    @staticmethod
    def _body_receiver(body: bytes):
        sent = False
        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return receive

    @staticmethod
    def _rewrite_new_training(body: bytes) -> bytes:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return body
        if not isinstance(payload, dict):
            return body
        payload["attendance_verified"] = False
        payload["success_verified"] = False
        if training_kind(payload.get("training_type"), payload.get("title")) == "work_start":
            payload["delivery_method"] = "Yüz yüze"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
