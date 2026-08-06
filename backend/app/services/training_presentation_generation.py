"""Atomic render, storage and download service for presentation versions.

The optional feature is fail-closed. It renders both PPTX and PDF from the
frozen manifest, validates hashes, writes only through the existing object-store
adapter, and marks the version generated only after both objects and the DB
transaction succeed. Any partial object is removed on failure.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import nace_training_presentation_active
from app.models.training_presentation import TrainingPresentationVersion
from app.services.object_store import ObjectStore, get_object_store
from app.services.training_presentation_renderer import (
    PDF_CONTENT_TYPE,
    PPTX_CONTENT_TYPE,
    RENDERER_VERSION,
    render_presentation,
    sha256_hex,
    verify_manifest,
)

logger = logging.getLogger(__name__)


class PresentationGenerationError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class PresentationDownload:
    content: bytes
    content_type: str
    filename: str
    file_hash: str


def _manifest(row: TrainingPresentationVersion) -> dict[str, Any]:
    try:
        value = json.loads(row.manifest_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PresentationGenerationError(
            "invalid_manifest_json",
            "Sunum sürümünün manifest JSON kaydı okunamadı.",
        ) from exc
    if not isinstance(value, dict):
        raise PresentationGenerationError(
            "invalid_manifest_json",
            "Sunum sürümünün manifest kaydı nesne olmalıdır.",
        )
    try:
        verify_manifest(value)
    except ValueError as exc:
        raise PresentationGenerationError("invalid_manifest_hash", str(exc)) from exc
    if str(value.get("content_hash") or "") != str(row.manifest_hash or ""):
        raise PresentationGenerationError(
            "manifest_snapshot_mismatch",
            "Sürüm manifest hash'i ile dondurulmuş kayıt uyuşmuyor.",
        )
    return value


def _safe_nace(value: str | None) -> str:
    clean = re.sub(r"[^0-9A-Za-z]+", "-", str(value or "nace")).strip("-").lower()
    return clean[:40] or "nace"


def output_storage_key(row: TrainingPresentationVersion, extension: str) -> str:
    ext = extension.strip().lower().lstrip(".")
    if ext not in {"pptx", "pdf"}:
        raise ValueError("Desteklenmeyen sunum çıktı türü.")
    return (
        f"training-presentations/company-{int(row.company_id)}/"
        f"training-{int(row.training_id)}/version-{int(row.version)}/"
        f"nace-{_safe_nace(row.nace_code)}-v{int(row.version)}.{ext}"
    )


def _cleanup(store: ObjectStore, keys: list[str]) -> list[str]:
    failed: list[str] = []
    for key in reversed(keys):
        try:
            store.delete(key)
        except Exception:
            failed.append(key)
            logger.exception("Sunum kısmi dosyası temizlenemedi: %s", key)
    return failed


def _clear_output_fields(row: TrainingPresentationVersion) -> None:
    row.pptx_storage_key = None
    row.pptx_file_hash = None
    row.pptx_file_size = None
    row.pptx_content_type = None
    row.pdf_storage_key = None
    row.pdf_file_hash = None
    row.pdf_file_size = None
    row.pdf_content_type = None
    row.generated_at = None


def _mark_failed(
    db: Session,
    row: TrainingPresentationVersion,
    *,
    code: str,
    detail: str,
) -> None:
    _clear_output_fields(row)
    row.status = "failed"
    row.failure_code = code[:80]
    row.failure_detail = detail[:2000]
    row.failed_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        logger.exception("Sunum başarısız durum kaydı yazılamadı: version_id=%s", row.id)


def generate_and_store_version(
    db: Session,
    *,
    row: TrainingPresentationVersion,
    store: ObjectStore | None = None,
) -> TrainingPresentationVersion:
    """Render and atomically persist both outputs for a draft/failed version."""
    if not nace_training_presentation_active(getattr(row, "company_id", None)):
        raise PresentationGenerationError(
            "pilot_access_denied",
            "NACE eğitim sunumu üretimi bu şirket için kontrollü pilot erişimine açık değildir.",
        )
    if row.status not in {"draft", "failed"}:
        raise PresentationGenerationError(
            "invalid_version_status",
            f"Yalnız taslak veya başarısız sürüm üretilebilir; mevcut durum: {row.status}.",
        )

    object_store = store or get_object_store()
    old_keys = [key for key in (row.pptx_storage_key, row.pdf_storage_key) if key]
    if old_keys:
        cleanup_failed = _cleanup(object_store, old_keys)
        if cleanup_failed:
            raise PresentationGenerationError(
                "stale_output_cleanup_failed",
                "Önceki kısmi sunum dosyaları temizlenemedi; yeni üretim başlatılmadı.",
            )
        _clear_output_fields(row)

    try:
        manifest = _manifest(row)
        rendered = render_presentation(manifest)
    except PresentationGenerationError as exc:
        _mark_failed(db, row, code=exc.code, detail=exc.detail)
        raise
    except Exception as exc:
        detail = f"Sunum renderer işlemi başarısız: {type(exc).__name__}."
        _mark_failed(db, row, code="renderer_failed", detail=detail)
        raise PresentationGenerationError("renderer_failed", detail) from exc

    pptx_hash = sha256_hex(rendered.pptx_bytes)
    pdf_hash = sha256_hex(rendered.pdf_bytes)
    pptx_key = output_storage_key(row, "pptx")
    pdf_key = output_storage_key(row, "pdf")
    stored: list[str] = []

    try:
        object_store.put_bytes(pptx_key, rendered.pptx_bytes)
        stored.append(pptx_key)
        object_store.put_bytes(pdf_key, rendered.pdf_bytes)
        stored.append(pdf_key)
    except Exception as exc:
        cleanup_failed = _cleanup(object_store, stored)
        detail = "PPTX/PDF depolama işlemi tamamlanamadı; kısmi dosyalar temizlendi."
        if cleanup_failed:
            detail = "Sunum depolama ve kısmi dosya temizleme işlemi başarısız oldu."
        _mark_failed(db, row, code="storage_failed", detail=detail)
        raise PresentationGenerationError("storage_failed", detail) from exc

    row.status = "generated"
    row.pptx_storage_key = pptx_key
    row.pptx_file_hash = pptx_hash
    row.pptx_file_size = len(rendered.pptx_bytes)
    row.pptx_content_type = PPTX_CONTENT_TYPE
    row.pdf_storage_key = pdf_key
    row.pdf_file_hash = pdf_hash
    row.pdf_file_size = len(rendered.pdf_bytes)
    row.pdf_content_type = PDF_CONTENT_TYPE
    row.generated_at = datetime.utcnow()
    row.failed_at = None
    row.failure_code = None
    row.failure_detail = None
    row.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        cleanup_failed = _cleanup(object_store, stored)
        detail = "Dosyalar üretildi ancak sürüm kaydı tamamlanamadı; dosyalar temizlendi."
        if cleanup_failed:
            detail = "Sürüm kaydı ve üretilen dosyaların temizlenmesi tamamlanamadı."
        raise PresentationGenerationError("database_commit_failed", detail) from exc
    return row


def read_generated_output(
    *,
    row: TrainingPresentationVersion,
    output_format: str,
    store: ObjectStore | None = None,
) -> PresentationDownload:
    """Read and hash-verify one historical output, independent of feature flag."""
    fmt = output_format.strip().lower().lstrip(".")
    if fmt == "pptx":
        key = row.pptx_storage_key
        expected_hash = row.pptx_file_hash
        content_type = row.pptx_content_type or PPTX_CONTENT_TYPE
    elif fmt == "pdf":
        key = row.pdf_storage_key
        expected_hash = row.pdf_file_hash
        content_type = row.pdf_content_type or PDF_CONTENT_TYPE
    else:
        raise PresentationGenerationError(
            "unsupported_output_format",
            "Yalnız PPTX veya PDF indirilebilir.",
        )
    if row.status not in {"generated", "approved", "archived"} or not key or not expected_hash:
        raise PresentationGenerationError(
            "output_not_ready",
            "İstenen sunum çıktısı henüz hazır değil.",
        )

    object_store = store or get_object_store()
    try:
        content = object_store.get_bytes(key)
    except Exception as exc:
        raise PresentationGenerationError(
            "output_missing",
            "Sunum dosyası depolamada bulunamadı.",
        ) from exc
    actual_hash = sha256_hex(content)
    if actual_hash != expected_hash:
        raise PresentationGenerationError(
            "output_hash_mismatch",
            "Sunum dosyası bütünlük kontrolünden geçemedi.",
        )
    filename = f"nace-egitim-{int(row.training_id)}-v{int(row.version)}.{fmt}"
    return PresentationDownload(
        content=content,
        content_type=content_type,
        filename=filename,
        file_hash=actual_hash,
    )


def generation_status_payload(row: TrainingPresentationVersion) -> dict[str, Any]:
    return {
        "version_id": row.id,
        "training_id": row.training_id,
        "version": row.version,
        "status": row.status,
        "renderer_version": RENDERER_VERSION,
        "outputs": {
            "pptx": {
                "ready": bool(row.pptx_storage_key and row.pptx_file_hash),
                "file_hash": row.pptx_file_hash,
                "file_size": row.pptx_file_size,
                "content_type": row.pptx_content_type,
            },
            "pdf": {
                "ready": bool(row.pdf_storage_key and row.pdf_file_hash),
                "file_hash": row.pdf_file_hash,
                "file_size": row.pdf_file_size,
                "content_type": row.pdf_content_type,
            },
        },
        "failure": {
            "code": row.failure_code,
            "detail": row.failure_detail,
        },
        "generated_at": row.generated_at,
        "core_training_unaffected": True,
    }
