"""Fail-closed security checks for ordinary personnel profile files.

This module rejects unsafe content before the shared upload helper can write a
quarantine copy to Render local storage. Profile photos are re-encoded without
metadata; DOCX/PDF/image containers are structurally inspected.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.services.clamav_scan import is_clamav_configured, scan_bytes
from app.services.upload_security import DENY_MAGIC, MAGIC_BY_EXT


_MAX_IMAGE_EDGE = 2048
_MAX_IMAGE_PIXELS = 40_000_000
_MAX_DOCX_UNCOMPRESSED = 50 * 1024 * 1024
_MAX_PDF_PAGES = 500
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_KIND_EXTENSIONS = {
    "profile_photo": _IMAGE_EXTENSIONS,
    "cv": {".pdf", ".docx"},
    "qualification": {".pdf", *_IMAGE_EXTENSIONS},
    "certificate": {".pdf", *_IMAGE_EXTENSIONS},
}
_KIND_BYTE_LIMITS = {
    "profile_photo": 5 * 1024 * 1024,
    "cv": 10 * 1024 * 1024,
    "qualification": 15 * 1024 * 1024,
    "certificate": 15 * 1024 * 1024,
}


def _reject_unsafe_content_without_quarantine(content: bytes, extension: str) -> None:
    head = content[:16]
    for denied in DENY_MAGIC:
        if head.startswith(denied):
            raise HTTPException(400, "Dosya içeriği güvenlik kontrolünden geçmedi.")

    expected = MAGIC_BY_EXT.get(extension)
    if not expected:
        raise HTTPException(400, "Desteklenmeyen dosya türü.")
    if extension == ".webp":
        valid = (
            content.startswith(b"RIFF")
            and len(content) >= 12
            and content[8:12] == b"WEBP"
        )
    else:
        valid = any(content.startswith(signature) for signature in expected)
    if not valid:
        raise HTTPException(
            400,
            "Dosya uzantısı ile içerik uyuşmuyor (içerik doğrulama).",
        )

    if is_clamav_configured():
        clean, _detail = scan_bytes(content)
        if not clean:
            raise HTTPException(400, "Dosya virüs taramasından geçmedi.")


def _validate_image_container(content: bytes) -> None:
    try:
        with Image.open(BytesIO(content)) as image:
            if int(image.width) * int(image.height) > _MAX_IMAGE_PIXELS:
                raise HTTPException(400, "Görüntü piksel sınırını aşıyor.")
            image.verify()
    except Image.DecompressionBombError as exc:
        raise HTTPException(400, "Görüntü piksel sınırını aşıyor.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(400, "Görüntü dosyası güvenli biçimde çözümlenemedi.") from exc


def _sanitize_profile_photo(content: bytes, extension: str) -> bytes:
    _validate_image_container(content)
    try:
        with Image.open(BytesIO(content)) as source:
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
    except Image.DecompressionBombError as exc:
        raise HTTPException(400, "Profil fotoğrafı piksel sınırını aşıyor.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            400,
            "Profil fotoğrafı güvenli biçimde çözümlenemedi.",
        ) from exc
    _reject_unsafe_content_without_quarantine(sanitized, extension)
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


def _resolve_pdf_object(value: Any) -> Any:
    try:
        return value.get_object()
    except AttributeError:
        return value


def _validate_pdf_container(content: bytes) -> None:
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise HTTPException(400, "Şifreli PDF yüklenemez.")
        if len(reader.pages) > _MAX_PDF_PAGES:
            raise HTTPException(400, "PDF sayfa sınırını aşıyor.")

        root = _resolve_pdf_object(reader.trailer.get("/Root"))
        if not isinstance(root, dict):
            raise HTTPException(400, "PDF kök yapısı doğrulanamadı.")
        if "/OpenAction" in root or "/AA" in root:
            raise HTTPException(400, "Aktif eylem içeren PDF yüklenemez.")

        names = _resolve_pdf_object(root.get("/Names"))
        if isinstance(names, dict) and (
            "/JavaScript" in names or "/EmbeddedFiles" in names
        ):
            raise HTTPException(400, "Aktif veya gömülü içerik içeren PDF yüklenemez.")

        blocked_actions = {
            "/JavaScript",
            "/Launch",
            "/SubmitForm",
            "/ImportData",
            "/GoToR",
        }
        for page in reader.pages:
            page_object = _resolve_pdf_object(page)
            if not isinstance(page_object, dict):
                continue
            if "/AA" in page_object:
                raise HTTPException(400, "Aktif eylem içeren PDF yüklenemez.")
            annotations = _resolve_pdf_object(page_object.get("/Annots")) or []
            for reference in annotations:
                annotation = _resolve_pdf_object(reference)
                if not isinstance(annotation, dict):
                    continue
                if "/AA" in annotation:
                    raise HTTPException(400, "Aktif eylem içeren PDF yüklenemez.")
                action = _resolve_pdf_object(annotation.get("/A"))
                if isinstance(action, dict) and str(action.get("/S")) in blocked_actions:
                    raise HTTPException(400, "Tehlikeli eylem içeren PDF yüklenemez.")
    except HTTPException:
        raise
    except (PdfReadError, OSError, TypeError, ValueError, KeyError) as exc:
        raise HTTPException(400, "PDF yapısı doğrulanamadı.") from exc


def prepare_profile_upload(
    content: bytes,
    *,
    filename: str,
    document_kind: str,
) -> bytes:
    """Validate and return bytes without writing rejected content to local disk."""

    limit = _KIND_BYTE_LIMITS.get(document_kind)
    allowed_extensions = _KIND_EXTENSIONS.get(document_kind)
    if limit is None or allowed_extensions is None:
        raise HTTPException(400, "Desteklenmeyen profil belge türü.")
    if not content:
        raise HTTPException(400, "Boş dosya yüklenemez.")
    if len(content) > limit:
        raise HTTPException(
            413,
            f"Dosya bu kategori için {limit // (1024 * 1024)} MB sınırını aşıyor.",
        )

    extension = Path(filename or "").suffix.lower()
    if extension not in allowed_extensions:
        raise HTTPException(400, "Bu profil belge türü için uzantı desteklenmiyor.")
    _reject_unsafe_content_without_quarantine(content, extension)

    if document_kind == "profile_photo":
        return _sanitize_profile_photo(content, extension)
    if extension == ".docx":
        _validate_docx_container(content)
    elif extension == ".pdf":
        _validate_pdf_container(content)
    elif extension in _IMAGE_EXTENSIONS:
        _validate_image_container(content)
    return content
