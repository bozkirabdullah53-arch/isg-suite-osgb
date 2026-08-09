"""Atomic storage lifecycle for Teaching V3 presentation outputs."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import nace_training_presentation_active
from app.models.training_presentation import TrainingPresentationVersion
from app.services.object_store import ObjectStore, get_object_store
from app.services.training_presentation_generation import (
    PresentationGenerationError,
    _cleanup,
    _clear_output_fields,
    _manifest,
    _mark_failed,
    output_storage_key,
)
from app.services.training_presentation_phase8 import phase8_active, validate_manifest_traceability
from app.services.training_presentation_renderer import PDF_CONTENT_TYPE, PPTX_CONTENT_TYPE, sha256_hex
from app.services.training_presentation_teaching_renderer import (
    TEACHING_RENDERER_VERSION,
    render_teaching_presentation,
)


def generate_and_store_teaching_version(
    db: Session,
    *,
    row: TrainingPresentationVersion,
    store: ObjectStore | None = None,
) -> TrainingPresentationVersion:
    """Render exactly the stored Teaching V3 manifest and persist both outputs."""
    if not nace_training_presentation_active(getattr(row, "company_id", None)):
        raise PresentationGenerationError("pilot_access_denied", "Ders Sunumu V3 bu şirket için kontrollü pilot erişimine açık değildir.")
    if row.status not in {"draft", "failed"}:
        raise PresentationGenerationError("invalid_version_status", f"Yalnız taslak veya başarısız sürüm üretilebilir; mevcut durum: {row.status}.")

    object_store = store or get_object_store()
    old_keys = [key for key in (row.pptx_storage_key, row.pdf_storage_key) if key]
    if old_keys:
        cleanup_failed = _cleanup(object_store, old_keys)
        if cleanup_failed:
            raise PresentationGenerationError("stale_output_cleanup_failed", "Önceki kısmi sunum dosyaları temizlenemedi; yeni üretim başlatılmadı.")
        _clear_output_fields(row)

    try:
        manifest = _manifest(row)
        if not bool((manifest.get("rendering") or {}).get("teaching_v3")):
            raise PresentationGenerationError("teaching_v3_not_ready", "Bu taslak Ders Sunumu V3 için zenginleştirilmemiş. Önce yeni V3 taslak oluşturun.")
        if phase8_active():
            validate_manifest_traceability(manifest)
        rendered = render_teaching_presentation(manifest)
    except PresentationGenerationError as exc:
        _mark_failed(db, row, code=exc.code, detail=exc.detail)
        raise
    except Exception as exc:
        detail = f"Ders Sunumu V3 renderer işlemi başarısız: {type(exc).__name__}."
        _mark_failed(db, row, code="teaching_renderer_failed", detail=detail)
        raise PresentationGenerationError("teaching_renderer_failed", detail) from exc

    pptx_hash = sha256_hex(rendered.pptx_bytes)
    pdf_hash = sha256_hex(rendered.pdf_bytes)
    pptx_key = output_storage_key(row, "pptx")
    pdf_key = output_storage_key(row, "pdf")
    stored: list[str] = []
    try:
        object_store.put_bytes(pptx_key, rendered.pptx_bytes); stored.append(pptx_key)
        object_store.put_bytes(pdf_key, rendered.pdf_bytes); stored.append(pdf_key)
    except Exception as exc:
        cleanup_failed = _cleanup(object_store, stored)
        detail = "Ders Sunumu V3 depolaması tamamlanamadı; kısmi dosyalar temizlendi."
        if cleanup_failed:
            detail = "Ders Sunumu V3 depolama ve kısmi dosya temizleme işlemi başarısız oldu."
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
        db.commit(); db.refresh(row)
    except Exception as exc:
        db.rollback()
        cleanup_failed = _cleanup(object_store, stored)
        detail = "V3 dosyaları üretildi ancak sürüm kaydı tamamlanamadı; dosyalar temizlendi."
        if cleanup_failed:
            detail = "V3 sürüm kaydı ve üretilen dosyaların temizlenmesi tamamlanamadı."
        raise PresentationGenerationError("database_commit_failed", detail) from exc
    return row


def teaching_generation_payload(row: TrainingPresentationVersion) -> dict:
    return {
        "version_id": row.id,
        "training_id": row.training_id,
        "version": row.version,
        "status": row.status,
        "renderer_version": TEACHING_RENDERER_VERSION,
        "teaching_v3": True,
        "outputs": {
            "pptx": {"ready": bool(row.pptx_storage_key and row.pptx_file_hash), "file_hash": row.pptx_file_hash, "file_size": row.pptx_file_size},
            "pdf": {"ready": bool(row.pdf_storage_key and row.pdf_file_hash), "file_hash": row.pdf_file_hash, "file_size": row.pdf_file_size},
        },
        "core_training_unaffected": True,
    }
