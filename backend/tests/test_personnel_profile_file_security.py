from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from PIL import Image
from reportlab.pdfgen import canvas

from app.api.personnel_profile_documents import (
    _TrackedObjectStore,
    _profile_storage_backend_allowed,
)
from app.api.personnel_profile_management import router as management_router
from app.services.personnel_profile_file_security import prepare_profile_upload


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, content: bytes) -> str:
        self.objects[key] = bytes(content)
        return key

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def resolve_local_path(self, key: str):
        return None


def _png(width: int = 3200, height: int = 120) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(
        output,
        format="PNG",
        pnginfo=None,
    )
    return output.getvalue()


def _pdf() -> bytes:
    output = BytesIO()
    document = canvas.Canvas(output)
    document.drawString(72, 760, "Authorized professional profile document")
    document.save()
    return output.getvalue()


def _zip(entries: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def test_profile_photo_is_decoded_resized_and_reencoded() -> None:
    original = _png()

    sanitized = prepare_profile_upload(
        original,
        filename="profile.png",
        document_kind="profile_photo",
    )

    assert sanitized.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(sanitized)) as image:
        assert image.width <= 2048
        assert image.height <= 2048
        assert image.getexif() == {}


def test_profile_photo_original_size_limit_is_checked_before_decode() -> None:
    with pytest.raises(HTTPException) as exc:
        prepare_profile_upload(
            b"x" * (5 * 1024 * 1024 + 1),
            filename="profile.png",
            document_kind="profile_photo",
        )
    assert exc.value.status_code == 413


def test_fake_image_is_rejected_even_with_allowed_extension() -> None:
    with pytest.raises(HTTPException) as exc:
        prepare_profile_upload(
            b"\x89PNG\r\n\x1a\nnot-an-image",
            filename="profile.png",
            document_kind="profile_photo",
        )
    assert exc.value.status_code == 400


def test_valid_pdf_passes_structural_validation() -> None:
    content = _pdf()

    prepared = prepare_profile_upload(
        content,
        filename="cv.pdf",
        document_kind="cv",
    )

    assert prepared == content


def test_fake_pdf_header_is_not_enough() -> None:
    with pytest.raises(HTTPException) as exc:
        prepare_profile_upload(
            b"%PDF-1.7\nnot-a-real-pdf\n%%EOF",
            filename="cv.pdf",
            document_kind="cv",
        )
    assert exc.value.status_code == 400


def test_docx_requires_real_office_package_structure() -> None:
    fake_docx = _zip({"random.txt": b"not a document"})

    with pytest.raises(HTTPException) as exc:
        prepare_profile_upload(
            fake_docx,
            filename="cv.docx",
            document_kind="cv",
        )
    assert exc.value.status_code == 400


def test_valid_minimum_docx_structure_passes_container_check() -> None:
    docx = _zip(
        {
            "[Content_Types].xml": b"<Types/>",
            "word/document.xml": b"<w:document/>",
        }
    )

    prepared = prepare_profile_upload(
        docx,
        filename="cv.docx",
        document_kind="cv",
    )

    assert prepared == docx


def test_docx_path_traversal_entry_is_rejected() -> None:
    dangerous = _zip(
        {
            "[Content_Types].xml": b"<Types/>",
            "word/document.xml": b"<w:document/>",
            "../escape.txt": b"blocked",
        }
    )

    with pytest.raises(HTTPException) as exc:
        prepare_profile_upload(
            dangerous,
            filename="cv.docx",
            document_kind="cv",
        )
    assert exc.value.status_code == 400


def test_tracked_store_removes_object_after_transaction_failure() -> None:
    delegate = MemoryStore()
    tracked = _TrackedObjectStore(delegate)

    tracked.put_bytes("private/random-object.pdf", b"payload")
    assert delegate.exists("private/random-object.pdf")

    tracked.cleanup_created()

    assert not delegate.exists("private/random-object.pdf")
    assert tracked.created_key is None


def test_profile_documents_require_remote_only_object_storage() -> None:
    assert _profile_storage_backend_allowed("r2") is True
    assert _profile_storage_backend_allowed("s3") is True
    assert _profile_storage_backend_allowed("minio") is True
    assert _profile_storage_backend_allowed("local") is False
    assert _profile_storage_backend_allowed("dual") is False
    assert _profile_storage_backend_allowed("") is False


def test_specific_document_archive_route_precedes_generic_archive_route() -> None:
    paths = [
        path
        for route in management_router.routes
        if (path := getattr(route, "path", None)) is not None
    ]
    document_path = next(
        index
        for index, path in enumerate(paths)
        if path.endswith("/{profile_id}/documents/{document_key}/archive")
    )
    generic_path = next(
        index
        for index, path in enumerate(paths)
        if path.endswith("/{profile_id}/{entry_type}/{entry_key}/archive")
    )

    assert document_path < generic_path
