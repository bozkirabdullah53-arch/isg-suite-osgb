"""Kalıcı silme koruması — gerekçe, önizleme ve silme öncesi arşiv.

İBYS Veritabanı Değişiklik Prosedürü §4-§7 gereksinimleri:

- Kalıcı silme geri alınamaz olduğundan **gerekçe zorunludur**.
- Toplu işlemler önce **dry-run önizleme** ile raporlanır.
- Silinen kayıtlar denetim izi için merkezi arşive JSON olarak yazılır ve
  ``audit_logs``'a eski değer olarak işlenir.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.models.entities import ArchiveKind, EisaArchiveRecord, User
from app.services.archive_store import _checksum, _rel_store, archive_root

logger = logging.getLogger(__name__)

MIN_DELETE_REASON_CHARS = 10
MAX_DELETE_REASON_CHARS = 500


def require_delete_reason(reason: str | None) -> str:
    """Kalıcı silme için gerekçeyi doğrular (min 10 karakter)."""
    cleaned = (reason or "").strip()
    if len(cleaned) < MIN_DELETE_REASON_CHARS:
        raise HTTPException(
            status_code=422,
            detail=(
                "Kalıcı silme için gerekçe zorunludur "
                f"(en az {MIN_DELETE_REASON_CHARS} karakter)."
            ),
        )
    return cleaned[:MAX_DELETE_REASON_CHARS]


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"encoding": "hex", "value": value.hex()}
    return value


def serialize_row(row: object) -> dict[str, Any]:
    """ORM satırını JSON-uyumlu sözlüğe çevirir."""
    return {
        column.key: _json_value(getattr(row, column.key, None))
        for column in sa_inspect(type(row)).columns
    }


def serialize_rows(rows: Iterable[object]) -> list[dict[str, Any]]:
    return [serialize_row(row) for row in rows]


def summarize_rows(rows: Iterable[object], *, limit: int = 50) -> list[dict[str, Any]]:
    """Önizleme için hafif özet (id + görünen ad)."""
    out: list[dict[str, Any]] = []
    for row in list(rows)[:limit]:
        out.append(
            {
                "id": getattr(row, "id", None),
                "label": getattr(row, "full_name", None)
                or getattr(row, "form_no", None)
                or getattr(row, "name", None)
                or getattr(row, "title", None),
                "company_id": getattr(row, "company_id", None),
            }
        )
    return out


def archive_records_before_delete(
    db: Session,
    *,
    rows: Iterable[object],
    entity_type: str,
    company_id: int | None,
    osgb_id: int | None = None,
    user: User | None = None,
    reason: str | None = None,
    entity_id: str | None = None,
    original_name: str | None = None,
) -> EisaArchiveRecord | None:
    """Silinecek kayıtları JSON olarak merkezi arşive yazar.

    Arşiv yazılamazsa ``RuntimeError`` yükseltir; çağıran silmeyi durdurmalıdır
    (fail-closed: kanıtsız silme yapılmaz).
    """
    payload_rows = list(rows)
    if not payload_rows:
        return None

    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    folder = (
        archive_root()
        / "deleted"
        / f"osgb-{osgb_id or 0}"
        / f"company-{company_id or 0}"
        / stamp
    )
    try:
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{entity_type}-{entity_id or 'bulk'}-{uuid4().hex[:10]}.json"
        payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "company_id": company_id,
            "osgb_id": osgb_id,
            "reason": reason,
            "deleted_by_user_id": user.id if user else None,
            "deleted_at": datetime.utcnow().isoformat() + "Z",
            "record_count": len(payload_rows),
            "records": serialize_rows(payload_rows),
        }
        dest.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.exception(
            "Silme öncesi arşiv yazılamadı; silme durduruldu: entity_type=%s", entity_type
        )
        raise RuntimeError(
            "Silme öncesi arşiv oluşturulamadı; veri kaybını önlemek için işlem durduruldu."
        ) from exc

    row = EisaArchiveRecord(
        kind=ArchiveKind.DELETED_FILE,
        osgb_id=osgb_id,
        company_id=company_id,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        original_name=original_name or dest.name,
        storage_path=_rel_store(dest),
        size_bytes=dest.stat().st_size,
        checksum=_checksum(dest),
        notes=(reason or "Silme öncesi otomatik arşiv")[:1000],
        created_by_user_id=user.id if user else None,
    )
    db.add(row)
    db.flush()
    return row
