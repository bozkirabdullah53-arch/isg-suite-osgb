"""Onaylı değişiklik talebini gerçek kayda uygulayan güvenli uygulayıcı (§5.3).

Yalnızca beyaz listedeki alanlar talep yoluyla değiştirilebilir. Uygulama
sırasında kaydın mevcut değeri talepteki ``old_value`` ile karşılaştırılır;
arada başkası değiştirdiyse çakışma (409) döner.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, Integer
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.models.entities import ChangeRequest, Company, Employee, IncidentEvent

logger = logging.getLogger(__name__)


class ApplyError(RuntimeError):
    """Uygulama sırasında iş kuralı ihlali."""


class ApplyConflict(ApplyError):
    """Kaydın mevcut değeri talepteki eski değerle uyuşmuyor."""


# Talep yoluyla değiştirilebilecek alanlar (fail-closed beyaz liste).
FIELD_WHITELIST: dict[str, dict[str, set[str]]] = {
    "employee": {
        "model": {"Employee"},
        "fields": {
            "full_name",
            "job_title",
            "department",
            "special_status",
            "start_date",
            "exit_date",
            "is_active",
        },
    },
    "company": {
        "model": {"Company"},
        "fields": {"name", "address", "phone", "authorized_person", "nace_code", "hazard_class"},
    },
    "incident": {
        "model": {"IncidentEvent"},
        "fields": {"sgk_report_date", "sgk_reported", "location", "department", "short_summary"},
    },
}

_MODEL_BY_ENTITY = {
    "employee": Employee,
    "company": Company,
    "incident": IncidentEvent,
}


def _coerce(column: Any, raw: Any) -> Any:
    """Metin değerini kolon tipine dönüştürür."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    column_type = column.type
    if isinstance(column_type, Boolean):
        return text.lower() in ("1", "true", "evet", "yes", "aktif", "x")
    if isinstance(column_type, (Date, DateTime)):
        cleaned = text.replace("Z", "")
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError as exc:
            raise ApplyError(f"'{text}' geçerli bir tarih değil.") from exc
        return parsed.date() if isinstance(column_type, Date) and not isinstance(column_type, DateTime) else parsed
    if isinstance(column_type, Integer):
        try:
            return int(float(text))
        except ValueError as exc:
            raise ApplyError(f"'{text}' geçerli bir sayı değil.") from exc
    if isinstance(column_type, Float):
        try:
            return float(text.replace(",", "."))
        except ValueError as exc:
            raise ApplyError(f"'{text}' geçerli bir sayı değil.") from exc
    return text


def _current_value(row: object, column_key: str) -> Any:
    value = getattr(row, column_key, None)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _values_match(current: Any, expected: Any) -> bool:
    if expected is None:
        return True
    if current is None:
        return False
    return str(current).strip() == str(expected).strip()


def apply_change(request: ChangeRequest, db: Session) -> dict:
    """Talebi hedef kayda uygular; özet döndürür. Hata halinde ApplyError yükseltir."""
    entity_type = (request.target_entity_type or "").strip().lower()
    rule = FIELD_WHITELIST.get(entity_type)
    if rule is None:
        raise ApplyError(
            f"'{entity_type}' varlık türü talep yoluyla değiştirilemez."
        )

    field_name = (request.field_name or "").strip()
    if not field_name:
        raise ApplyError("Uygulanacak alan belirtilmemiş.")
    if field_name not in rule["fields"]:
        raise ApplyError(
            f"'{field_name}' alanı talep yoluyla değiştirilemez (beyaz liste dışı)."
        )

    model = _MODEL_BY_ENTITY.get(entity_type)
    if model is None:
        raise ApplyError("Hedef kayıt modeli bulunamadı.")

    try:
        target_id = int(str(request.target_entity_id or "").strip())
    except ValueError as exc:
        raise ApplyError("Hedef kayıt kimliği geçersiz.") from exc

    row = db.get(model, target_id)
    if row is None:
        raise ApplyError("Hedef kayıt bulunamadı.")

    if request.company_id is not None and getattr(row, "company_id", None) != request.company_id:
        raise ApplyError("Hedef kayıt talep edilen firma kapsamında değil.")

    mapper = sa_inspect(type(row))
    column = mapper.columns.get(field_name)
    if column is None:
        raise ApplyError(f"'{field_name}' alanı bu kayıtta bulunmuyor.")

    current = _current_value(row, field_name)
    if not _values_match(current, request.old_value):
        raise ApplyConflict(
            f"Kaydın mevcut değeri ({current}) talepteki eski değerle uyuşmuyor; "
            "arada başka bir değişiklik yapılmış olabilir."
        )

    new_value = _coerce(column, request.requested_value)
    setattr(row, field_name, new_value)
    db.flush()
    return {
        "entity_type": entity_type,
        "entity_id": target_id,
        "field_name": field_name,
        "old_value": current,
        "new_value": _current_value(row, field_name),
    }


def parse_requested_value(raw: str | None) -> Any:
    """Talep değeri JSON ise çözer; değilse metin olarak döndürür."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.startswith(("{", "[")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text
