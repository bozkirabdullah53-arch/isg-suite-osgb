"""Ek güvenlik kontrolleri for ordinary personnel profile files.

Profil fotoğrafları metadata temizlenerek yeniden kodlanır. DOCX dosyaları yalnız
geçerli Office Open XML paket yapısına sahipse kabul edilir.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.upload_security import assert_safe_upload


_MAX_IMAGE_EDGE = 2048
_MAX_IMAGE_PIXELS = 40_000_000
_MAX_DOCX_UNCOMPRESSED = 50 * 1024 * 1024
_KIND_BYTE_LIMITS = {
    "profile_photo": 5 * 1024 * 1024,
    "cv": 10 * 1024 * 1024,
    "qualification": 15 * 1024 * 1024,
    "certificate": 15 * 1024 * 1024,
}


def _sanitize_profile_photo(content: bytes, extension: str) -> bytes:
    try:
        with Image.open(BytesIO(content)) as probe:
            if int(probe.width) * int(probe.height) > _MAX_IMAGE_PIXELS:
                raise HTTPException(400, "Profil fotoğrafı piksel sınırını aşıyor.")
            probe.verify()
        with Image.open(BytesIO(content)) as source:
            if int(source.width) * int(source.height) > _MAX_IMAGE_PIXELS:
                raise HTTPException(400, "Profil fotoğrafı piksel sınırını aşıyor.")
            image = ImageOps.exif_transpose(source)
            image.thumbnail((_MAX_IMAGE_EDGE, _MAX_IMAGE_EDGE))
            output = BytesIO()
            if extension in {".jpg", ".jpeg"}:
                image.convert("RGB").save(
                    output,
                    format="JPEG",
                    quality=90,
                    optimize=True,
                )
            elif extension == ".png":
                mode = "RGBA" if "A" in image.getbands() else "RGB"
                image.convert(mode).save(output, format="PNG", optimize=True)
            elif extension == ".webp":
                mode = "RGBA" if "A" in image.getbands() else "RGB"
                image.convert(mode).save(
                    output,
                    format="WEBP",
                    quality=90,
                    method=6,
                )
            else:
                raise HTTPException(400, "Desteklenmeyen profil fotoğrafı türü.")
            sanitized = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            400,
            "Profil fotoğrafı güvenli biçimde çözümlenemedi.",
        ) from exc
    assert_safe_upload(sanitized, extension, "sanitized-profile-photo")
    return sanitized


def _validate_docx_container(content: bytes) -> None:
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            required = {"[Content_Types].xml", "word/document.xml"}
            if not required.issubset(names):
                raise HTTPException(400, "DOCX paket yapısı doğrulanamadı.")
            total_uncompressed = 0
            for item in archive.infolist():
                normalized = item.filename.replace("\\", "/")
                parts = [part for part in normalized.split("/") if part]
                if any(part in {".", ".."} for part in parts):
                    raise HTTPException(400, "DOCX içinde geçersiz yol bulundu.")
                total_uncompressed += int(item.file_size)
                if total_uncompressed > _MAX_DOCX_UNCOMPRESSED:
                    raise HTTPException(400, "DOCX açılmış boyut sınırını aşıyor.")
    except BadZipFile as exc:
        raise HTTPException(400, "DOCX paketi bozuk veya geçersiz.") from exc


def prepare_profile_upload(
    content: bytes,
    *,
    filename: str,
    document_kind: str,
) -> bytes:
    """Return safe bytes without changing the original filename contract."""

    limit = _KIND_BYTE_LIMITS.get(document_kind)
    if limit is None:
        raise HTTPException(400, "Desteklenmeyen profil belge türü.")
    if not content:
        raise HTTPException(400, "Boş dosya yüklenemez.")
    if len(content) > limit:
        raise HTTPException(
            413,
            f"Dosya bu kategori için {limit // (1024 * 1024)} MB sınırını aşıyor.",
        )

    extension = Path(filename or "").suffix.lower()
    if document_kind == "profile_photo":
        return _sanitize_profile_photo(content, extension)
    if extension == ".docx":
        _validate_docx_container(content)
    return content
