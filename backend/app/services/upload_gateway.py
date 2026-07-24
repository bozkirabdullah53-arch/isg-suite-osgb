"""Tekil upload gateway iskeleti (P0) — varsayılan kapalı, çağıranları bozmaz.

Envanter (write_bytes / UploadFile yolları — aşamalı taşınacak):
  - app/api/files.py          → /files/documents/{id}
  - app/api/health.py         → sağlık ekleri
  - app/api/trainings.py      → eğitim belgeleri
  - app/api/risks.py          → risk medya
  - app/api/ppe.py            → KKD
  - app/api/operations.py     → ziyaret / operasyon
  - app/api/osgb.py           → OSGB ekleri
  - app/api/drills.py         → tatbikat
  - app/api/emergency_teams.py
  - app/api/annual_eval.py
  - app/services/archive_store.py (şifreli arşiv — ayrı yol)

Flag: settings.upload_gateway_enabled=False iken persist_upload kullanılmaz;
mevcut endpoint'ler assert_safe_upload + doğrudan yazmaya devam eder.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import settings
from app.services.upload_security import assert_safe_upload


def upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def persist_upload(
    content: bytes,
    *,
    company_id: int,
    extension: str,
    original_name: str = "",
    subdir: str = "",
) -> tuple[Path, str]:
    """Güvenli yazma: magic/AV + path jail + boyut.

    Döner: (absolute_path, stored_relative_name).
    Yalnızca upload_gateway_enabled=True iken yeni kod yollarından çağrılmalı.
    """
    if not settings.upload_gateway_enabled:
        raise RuntimeError("upload_gateway_enabled=False — mevcut endpoint yollarını kullanın.")

    ext = (extension or "").lower()
    if not ext.startswith("."):
        ext = f".{ext}" if ext else ""

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")

    assert_safe_upload(content, ext, original_name)

    company_dir = upload_root() / str(int(company_id))
    if subdir:
        safe_sub = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in subdir)[:64]
        company_dir = company_dir / safe_sub
    company_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}{ext}"
    target = (company_dir / stored_name).resolve()
    if upload_root() not in target.parents:
        raise HTTPException(status_code=400, detail="Geçersiz dosya yolu.")

    target.write_bytes(content)
    return target, stored_name
