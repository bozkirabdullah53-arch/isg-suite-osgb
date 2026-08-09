"""Additive 2026 training lifecycle and duration policy.

The service is deliberately data-migration free. Existing persisted training,
exam, presentation, PDF, certificate and attendance records are never rewritten.
New behavior is gated by environment flags and an optional cutover timestamp.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
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
