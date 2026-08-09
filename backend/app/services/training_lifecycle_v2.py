"""Additive 2026 training lifecycle and duration policy.

The service is deliberately data-migration free. Existing persisted training,
exam, presentation, PDF, certificate and attendance records are never rewritten.
New behavior is gated by environment flags and an optional cutover timestamp.

Implementation strategy:
- patch only the training-create duration resolver while the flag is active;
- rewrite only NEW training-create JSON at the HTTP boundary so planning never
  pre-confirms attendance/success;
- block the legacy direct-complete PATCH only for post-cutover records;
- leave every historical record and legacy path unchanged when the flag is off.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from starlette.responses import JSONResponse

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

_START_TOKENS = (
    "işe başlama",
    "ise baslama",
)
_REPEAT_TOKENS = (
    "tekrar",
    "yenileme eğitimi",
    "yenileme egitimi",
)
_INFORMATION_REFRESH_TOKENS = (
    "bilgi yenileme",
    "bilgi tazeleme",
)

_original_resolve_training_hours = None


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
    return " ".join(str(value or "").strip().casefold().split())


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
    kind = training_kind(training_type, title)
    delivery = delivery_policy(
        training_type=training_type,
        title=title,
        hazard_class=hazard_class,
    )
    return {
        "version": POLICY_VERSION,
        "kind": kind,
        "duration_hours": duration_hours(
            training_type=training_type,
            title=title,
            hazard_class=hazard_class,
        ),
        "work_specific_hours": int(WORK_SPECIFIC_HOURS.get(hazard_class, 2)),
        "renewal_years": RENEWAL_YEARS.get(hazard_class),
        "lesson_definition": "1 ders saati = 45 dakika ders + 15 dakika ara dinlenmesi",
        "delivery": delivery,
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
            "work_start": {
                "label": "İşe Başlama Eğitimi",
                "minimum_hours": 2,
                "delivery": "Yüz yüze",
            },
            "initial_basic": {
                "label": "İlk Temel İSG Eğitimi",
                "hours": dict(INITIAL_BASIC_HOURS),
            },
            "repeat_basic": {
                "label": "Tekrar Temel İSG Eğitimi",
                "hours": dict(REPEAT_BASIC_HOURS),
            },
            "information_refresh": {
                "label": "Bilgi Yenileme Eğitimi",
                "work_specific_hours": dict(WORK_SPECIFIC_HOURS),
            },
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


def install_training_lifecycle_v2() -> dict[str, str]:
    """Wrap ONLY training-create duration resolution, idempotently.

    The legacy resolver remains the source of truth for special training profiles
    and for every request while the feature is disabled. No stored row is read or
    rewritten here.
    """
    global _original_resolve_training_hours

    from app.api import trainings
    from app.schemas import training as training_schema
    from app.services.special_training_profiles import resolve_special_duration_hours

    current = training_schema.resolve_training_hours
    if getattr(current, "_premium_training_lifecycle_v2", False):
        return {"duration_policy": "already-active"}

    _original_resolve_training_hours = current

    def premium_resolve_training_hours(
        *,
        training_type: str,
        title: str,
        notes: str | None,
        hazard_class: str,
    ) -> int:
        if not applies_to_new_request():
            return int(
                _original_resolve_training_hours(
                    training_type=training_type,
                    title=title,
                    notes=notes,
                    hazard_class=hazard_class,
                )
            )

        special = resolve_special_duration_hours(
            SimpleNamespace(training_type=training_type, title=title, notes=notes or "")
        )
        if special:
            return int(special)

        return duration_hours(
            training_type=training_type,
            title=title,
            hazard_class=hazard_class,
        )

    premium_resolve_training_hours._premium_training_lifecycle_v2 = True
    training_schema.resolve_training_hours = premium_resolve_training_hours
    # app.api.trainings imported the resolver directly at module import time.
    trainings.resolve_training_hours = premium_resolve_training_hours
    return {"duration_policy": "active"}


class PremiumTrainingLifecycleMiddleware:
    """Narrow HTTP guard for planning semantics and unsafe direct completion.

    It touches only:
    - POST /api/v1/trainings JSON for post-cutover NEW records;
    - PATCH /api/v1/trainings/{id} when an unsafe direct `completed` status is
      requested for a post-cutover record.

    All other requests are byte-for-byte delegated to the existing application.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not premium_lifecycle_active():
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "").upper()
        path = str(scope.get("path") or "")

        if method == "POST" and path.rstrip("/") == "/api/v1/trainings" and applies_to_new_request():
            body, receive = await self._read_body(receive)
            rewritten = self._rewrite_new_training(body)
            await self.app(scope, self._body_receiver(rewritten), send)
            return

        if method == "PATCH" and path.startswith("/api/v1/trainings/"):
            suffix = path.removeprefix("/api/v1/trainings/").strip("/")
            if suffix.isdigit():
                body, _original_receive = await self._read_body(receive)
                if self._requests_unsafe_completion(body):
                    if self._record_is_post_cutover(int(suffix)):
                        response = JSONResponse(
                            status_code=409,
                            content={
                                "detail": (
                                    "Bu yeni eğitim doğrudan 'Tamamlandı' yapılamaz. "
                                    "Önce Katılım ve Sonuçları Yönet ekranından katılım/puanları "
                                    "kaydedin, ardından Sonuçları Kesinleştir adımını kullanın."
                                )
                            },
                        )
                        await response(scope, self._body_receiver(b""), send)
                        return
                await self.app(scope, self._body_receiver(body), send)
                return

        await self.app(scope, receive, send)

    @staticmethod
    async def _read_body(receive):
        chunks: list[bytes] = []
        more = True
        while more:
            message = await receive()
            if message.get("type") != "http.request":
                continue
            chunks.append(message.get("body", b""))
            more = bool(message.get("more_body"))
        return b"".join(chunks), receive

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

        # Planning is not proof of attendance or success.
        payload["attendance_verified"] = False
        payload["success_verified"] = False

        kind = training_kind(payload.get("training_type"), payload.get("title"))
        if kind == "work_start":
            payload["delivery_method"] = "Yüz yüze"

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _requests_unsafe_completion(body: bytes) -> bool:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return isinstance(payload, dict) and str(payload.get("status") or "").casefold() == "completed"

    @staticmethod
    def _record_is_post_cutover(training_id: int) -> bool:
        from app.core.database import SessionLocal
        from app.models.entities import TrainingSession

        with SessionLocal() as db:
            row = db.get(TrainingSession, training_id)
            return bool(row and applies_to_created_at(getattr(row, "created_at", None)))
