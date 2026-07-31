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
from app.services.object_store import get_object_store
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
    """Güvenli yazma: magic/AV + object store + path jail + boyut.

    Döner: (absolute_path | placeholder, stored_relative_name).
    Uzak backend'de Path upload_root altında sanal anahtarı işaret eder (FileResponse
    için resolve_local_path None ise çağıran stream kullanmalı — henüz cutover yok).
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

    stored_name = f"{uuid4().hex}{ext}"
    parts = [str(int(company_id))]
    if subdir:
        safe_sub = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in subdir)[:64]
        parts.append(safe_sub)
    parts.append(stored_name)
    key = "/".join(parts)

    store = get_object_store()
    store.put_bytes(key, content)
    local = store.resolve_local_path(key)
    if local is not None:
        return local, stored_name
    # Uzak: geriye uyum için key'i Path gibi değil stored_name + key metadata
    # Şimdilik local-only production; uzak cutover ayrı PR.
    return upload_root() / key, stored_name


def persist_relative(
    content: bytes,
    *,
    relative_path: str,
    original_name: str = "",
    max_bytes: int | None = None,
) -> Path:
    """Mevcut rel path düzenini koruyarak gateway üzerinden yazar.

    Örn: ``42/health/7_abc.pdf`` → upload_dir altında aynı göreli yol.
    """
    if not settings.upload_gateway_enabled:
        raise RuntimeError("upload_gateway_enabled=False — mevcut endpoint yollarını kullanın.")

    rel = (relative_path or "").replace("\\", "/").strip("/")
    parts = [p for p in rel.split("/") if p and p != ".."]
    if not parts:
        raise HTTPException(status_code=400, detail="Geçersiz dosya yolu.")
    key = "/".join(parts)
    ext = Path(key).suffix.lower()
    if not ext:
        raise HTTPException(status_code=400, detail="Dosya uzantısı gerekli.")

    limit = max_bytes if max_bytes is not None else settings.max_upload_mb * 1024 * 1024
    if len(content) > limit:
        mb = max(1, limit // (1024 * 1024))
        raise HTTPException(status_code=413, detail=f"Dosya {mb} MB sınırını aşıyor.")

    assert_safe_upload(content, ext, original_name)
    store = get_object_store()
    store.put_bytes(key, content)
    local = store.resolve_local_path(key)
    if local is not None:
        return local
    return upload_root() / key
