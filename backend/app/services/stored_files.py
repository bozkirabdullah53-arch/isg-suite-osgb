"""Depolanan dosya indirme — local veya S3 (P0-03 cutover hazırlığı).

S3 backend'de eski local dosyalar için disk fallback.
Upload gateway / S3 flag kapalıyken davranış local FileResponse ile aynı.
"""
from __future__ import annotations

import io
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.services.object_store import LocalObjectStore, get_object_store


def response_for_storage_key(
    relative_key: str,
    *,
    filename: str | None = None,
    media_type: str = "application/octet-stream",
):
    """Göreli anahtar (örn. ``12/docs/a.pdf``) için FileResponse veya stream."""
    key = (relative_key or "").replace("\\", "/").strip("/")
    if not key or ".." in key.split("/"):
        raise HTTPException(status_code=400, detail="Geçersiz dosya yolu.")

    name = filename or Path(key).name
    store = get_object_store()

    local = store.resolve_local_path(key)
    if local is not None and local.is_file():
        return FileResponse(local, filename=name, media_type=media_type)

    if store.exists(key):
        data = store.get_bytes(key)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}",
        }
        return StreamingResponse(io.BytesIO(data), media_type=media_type, headers=headers)

    # S3 cutover öncesi / sırası: eski disk dosyaları
    legacy = LocalObjectStore().resolve_local_path(key)
    if legacy is not None and legacy.is_file():
        return FileResponse(legacy, filename=name, media_type=media_type)

    raise HTTPException(status_code=404, detail="Dosya fiziksel depolamada bulunamadı.")
