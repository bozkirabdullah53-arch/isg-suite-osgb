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
    image = Image.new("RGB", (width, height), "white")
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _pdf_with_embedded_attachment() -> bytes:
    base = BytesIO()
    page = canvas.Canvas(base)
    page.drawString(72, 720, "Personel belgesi")
    page.save()
    payload = base.getvalue()

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(BytesIO(payload))
    writer = PdfWriter()
    for page_obj in reader.pages:
        writer.add_page(page_obj)
    writer.add_attachment("gizli.txt", b"gizli")
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _zip_with_traversal() -> bytes:
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr("../evil.txt", b"evil")
    return out.getvalue()


def _zip_with_too_many_members(count: int = 260) -> bytes:
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        for index in range(count):
            archive.writestr(f"file-{index}.txt", b"x")
    return out.getvalue()


def test_png_is_normalized_and_size_limited() -> None:
    prepared = prepare_profile_upload(
        filename="kimlik.png",
        mime_type="image/png",
        content=_png(),
        document_kind="identity",
    )
    assert prepared.extension == ".png"
    assert prepared.mime_type == "image/png"
    assert prepared.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert prepared.file_size <= 3 * 1024 * 1024


def test_pdf_embedded_file_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        prepare_profile_upload(
            filename="belge.pdf",
            mime_type="application/pdf",
            content=_pdf_with_embedded_attachment(),
            document_kind="general",
        )
    assert exc_info.value.status_code == 422
    assert "ek dosya" in str(exc_info.value.detail).lower()


def test_zip_path_traversal_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        prepare_profile_upload(
            filename="arsiv.zip",
            mime_type="application/zip",
            content=_zip_with_traversal(),
            document_kind="general",
        )
    assert exc_info.value.status_code == 422


def test_zip_member_limit_is_enforced() -> None:
    with pytest.raises(HTTPException) as exc_info:
        prepare_profile_upload(
            filename="arsiv.zip",
            mime_type="application/zip",
            content=_zip_with_too_many_members(),
            document_kind="general",
        )
    assert exc_info.value.status_code == 422
    assert "çok fazla" in str(exc_info.value.detail).lower()


def test_dangerous_archive_extension_is_rejected() -> None:
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr("payload.exe", b"MZ")
    with pytest.raises(HTTPException) as exc_info:
        prepare_profile_upload(
            filename="arsiv.zip",
            mime_type="application/zip",
            content=out.getvalue(),
            document_kind="general",
        )
    assert exc_info.value.status_code == 422


def test_wrong_extension_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        prepare_profile_upload(
            filename="kimlik.jpg",
            mime_type="image/jpeg",
            content=_png(width=320, height=120),
            document_kind="identity",
        )
    assert exc_info.value.status_code == 422


def test_profile_storage_policy_rejects_local_and_dual() -> None:
    assert _profile_storage_backend_allowed("local") is False
    assert _profile_storage_backend_allowed("dual") is False
    assert _profile_storage_backend_allowed("s3") is True
    assert _profile_storage_backend_allowed("r2") is True
    assert _profile_storage_backend_allowed("minio") is True


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
    # FastAPI 0.141 may retain an internal _IncludedRouter sentinel alongside
    # concrete APIRoute entries. It has no public path and does not participate
    # in URL matching, so route-order assertions must inspect only real routes.
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
