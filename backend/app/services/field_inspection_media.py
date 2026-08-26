"""Görsel saha denetimi fotoğraf türevleri ve işaretleme çizimi."""
from __future__ import annotations

import json
from io import BytesIO
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.services.object_store import get_object_store


def prepare_photo_variants(
    content: bytes,
    *,
    privacy_blur: bool = False,
    rotation_degrees: int = 0,
    crop_to_square: bool = False,
) -> tuple[bytes, bytes, int, int]:
    """Orijinali değiştirmeden analiz ve önizleme JPEG türevleri üretir."""
    with Image.open(BytesIO(content)) as source:
        source.verify()
    with Image.open(BytesIO(content)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        rotation = int(rotation_degrees or 0) % 360
        if rotation in {90, 180, 270}:
            image = image.rotate(-rotation, expand=True)
        if crop_to_square:
            side = min(image.size)
            left = (image.width - side) // 2
            top = (image.height - side) // 2
            image = image.crop((left, top, left + side, top + side))
        width, height = image.size
        analysis = image.copy()
        analysis.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        preview = image.copy()
        preview.thumbnail((720, 720), Image.Resampling.LANCZOS)
        if privacy_blur:
            # Orijinal kanıt hiç değişmez. Bu seçenek, analiz/önizleme türevinde
            # hassas ayrıntıları genel olarak yumuşatır; otomatik yüz/plaka
            # tanıma iddiasında bulunmaz ve kullanıcıya açıkça gösterilir.
            analysis = analysis.filter(ImageFilter.GaussianBlur(radius=2.2))
            preview = preview.filter(ImageFilter.GaussianBlur(radius=1.4))
        analysis_buffer, preview_buffer = BytesIO(), BytesIO()
        analysis.save(analysis_buffer, format="JPEG", quality=88, optimize=True)
        preview.save(preview_buffer, format="JPEG", quality=78, optimize=True)
        return analysis_buffer.getvalue(), preview_buffer.getvalue(), width, height


def store_photo_variants(*, paths: dict[str, str], original: bytes, analysis: bytes, preview: bytes) -> None:
    store = get_object_store()
    store.put_bytes(paths["original"], original)
    store.put_bytes(paths["analysis"], analysis)
    # Marked ilk yüklemede analiz kopyasının bağımsız nesnesidir; orijinal asla
    # üzerine yazılmaz. Sonraki annotation çağrıları yalnız marked nesnesini yeniler.
    store.put_bytes(paths["marked"], analysis)
    store.put_bytes(paths["preview"], preview)


def _font(size: int):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _clamp(value: float | int | None, fallback: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback


def render_marked_photo(*, analysis_bytes: bytes, annotations: Iterable[object]) -> bytes:
    """Normalize koordinatları piksele çevirip aktif annotation'ları çizer."""
    with Image.open(BytesIO(analysis_bytes)) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    for index, annotation in enumerate(annotations, start=1):
        if getattr(annotation, "is_deleted", False):
            continue
        color = str(getattr(annotation, "color", "#dc2626") or "#dc2626")
        x = int(_clamp(getattr(annotation, "x", 0)) * width)
        y = int(_clamp(getattr(annotation, "y", 0)) * height)
        w = int(_clamp(getattr(annotation, "width", 0)) * width)
        h = int(_clamp(getattr(annotation, "height", 0)) * height)
        shape = str(getattr(annotation, "shape_type", "rectangle"))
        if shape in {"rectangle", "region"}:
            draw.rectangle((x, y, min(width - 1, x + w), min(height - 1, y + h)), outline=color, width=max(3, width // 350))
        elif shape == "point":
            radius = max(8, min(width, height) // 80)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=max(3, width // 350))
        elif shape == "arrow":
            draw.line((x, y, min(width - 1, x + w), min(height - 1, y + h)), fill=color, width=max(3, width // 350))
        elif shape == "polygon":
            try:
                points = json.loads(getattr(annotation, "points_json", "[]") or "[]")
                pixels = [(int(_clamp(p[0]) * width), int(_clamp(p[1]) * height)) for p in points if isinstance(p, list) and len(p) == 2]
            except (TypeError, ValueError, json.JSONDecodeError):
                pixels = []
            if len(pixels) >= 3:
                draw.line([*pixels, pixels[0]], fill=color, width=max(3, width // 350))
        label = str(getattr(annotation, "label", "") or f"#{index}")[:80]
        if label:
            font = _font(max(18, min(42, width // 45)))
            box = draw.textbbox((x, y), label, font=font)
            draw.rectangle((box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3), fill=color)
            draw.text((x, y), label, fill="white", font=font)
    output = BytesIO()
    image.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def replace_marked_photo(*, marked_path: str, content: bytes) -> None:
    get_object_store().put_bytes(marked_path, content)
