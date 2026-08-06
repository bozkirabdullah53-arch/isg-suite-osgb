from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from PIL import Image

from app.services.personnel_profile_file_security import prepare_profile_upload


def _png(width: int = 3200, height: int = 120) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(
        output,
        format="PNG",
        pnginfo=None,
    )
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


def test_fake_image_is_rejected_even_with_allowed_extension() -> None:
    with pytest.raises(HTTPException) as exc:
        prepare_profile_upload(
            b"\x89PNG\r\n\x1a\nnot-an-image",
            filename="profile.png",
            document_kind="profile_photo",
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
