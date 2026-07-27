"""Kullanıcı e-imza profili: görsel damga + yerel/nitelikli köprü durumu.

Katman 1 — Görsel imza (PNG/JPEG): PDF kutularına basılır (hemen kullanılabilir).
Katman 2 — Köprü (E_SIGN_BRIDGE_URL): kartlı/nitelikli e-imza ajanı hazır mı diye probe.
"""
from __future__ import annotations

import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import User
from app.services.upload_gateway import persist_relative
from app.services.upload_security import assert_safe_upload

BridgeStatus = Literal["not_configured", "ready", "unreachable", "error"]
MAX_SIG_BYTES = 350_000
ALLOWED_EXT = {".png", ".jpg", ".jpeg"}


def _upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def has_visual_signature(user: User) -> bool:
    return bool(getattr(user, "e_signature_storage_path", None))


def signature_status(user: User) -> dict[str, Any]:
    path = getattr(user, "e_signature_storage_path", None)
    bridge_url = (settings.e_sign_bridge_url or "").strip()
    return {
        "has_image": bool(path),
        "file_name": getattr(user, "e_signature_file_name", None),
        "uploaded_at": getattr(user, "e_signature_uploaded_at", None),
        "title": getattr(user, "e_signature_title", None) or None,
        "preview_url": "/security/e-signature/image" if path else None,
        "bridge_configured": bool(bridge_url),
        "bridge_status": getattr(user, "e_signature_bridge_status", None) or (
            "not_configured" if not bridge_url else "unknown"
        ),
        "bridge_checked_at": getattr(user, "e_signature_bridge_checked_at", None),
        "layers": {
            "visual": "ready" if path else "missing",
            "qualified_bridge": "configured" if bridge_url else "not_configured",
        },
        "note": (
            "Görsel imza PDF’lere basılır. Nitelikli e-imza için köprü URL’si "
            "(E_SIGN_BRIDGE_URL) ve kartlı imza ajanı gerekir — iBYSiS HSNSigner "
            "modelinden bağımsız, sunucu yapılandırmalı köprü."
        ),
    }


def read_signature_bytes(user: User) -> bytes | None:
    rel = getattr(user, "e_signature_storage_path", None)
    if not rel:
        return None
    path = (_upload_root() / rel).resolve()
    root = _upload_root()
    if root not in path.parents and path != root:
        return None
    if not path.is_file():
        return None
    data = path.read_bytes()
    if len(data) < 32 or len(data) > MAX_SIG_BYTES:
        return None
    return data


def save_signature_image(
    db: Session,
    user: User,
    *,
    raw: bytes,
    original_name: str,
) -> User:
    name = (original_name or "imza.png").strip() or "imza.png"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("Yalnızca PNG veya JPEG imza görseli yükleyin.")
    if len(raw) < 64:
        raise ValueError("İmza dosyası boş görünüyor.")
    if len(raw) > MAX_SIG_BYTES:
        raise ValueError("İmza dosyası çok büyük (max ~350 KB).")
    # assert_safe_upload HTTPException fırlatabilir — API katmanına geçsin
    assert_safe_upload(raw, ext, name)

    # Eski dosyayı sil
    old_rel = getattr(user, "e_signature_storage_path", None)
    if old_rel:
        old = (_upload_root() / old_rel).resolve()
        if _upload_root() in old.parents and old.exists():
            try:
                old.unlink()
            except OSError:
                pass

    scope = user.osgb_id or user.company_id or "user"
    rel = f"{scope}/e-sign/{user.id}_{uuid4().hex[:10]}{ext}"
    if settings.upload_gateway_enabled:
        persist_relative(raw, relative_path=rel, original_name=f"e-imza{ext}", max_bytes=MAX_SIG_BYTES)
    else:
        target = _upload_root() / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)

    user.e_signature_file_name = f"e-imza{ext}"
    user.e_signature_storage_path = rel.replace("\\", "/")
    user.e_signature_uploaded_at = datetime.utcnow()
    db.add(user)
    db.flush()
    return user


def clear_signature_image(db: Session, user: User) -> User:
    rel = getattr(user, "e_signature_storage_path", None)
    if rel:
        old = (_upload_root() / rel).resolve()
        if _upload_root() in old.parents and old.exists():
            try:
                old.unlink()
            except OSError:
                pass
    user.e_signature_file_name = None
    user.e_signature_storage_path = None
    user.e_signature_uploaded_at = None
    db.add(user)
    db.flush()
    return user


def set_signature_title(db: Session, user: User, title: str | None) -> User:
    cleaned = (title or "").strip()[:120] or None
    user.e_signature_title = cleaned
    db.add(user)
    db.flush()
    return user


def probe_bridge(user: User, db: Session | None = None) -> dict[str, Any]:
    url = (settings.e_sign_bridge_url or "").strip()
    started = time.perf_counter()
    if not url:
        status: BridgeStatus = "not_configured"
        result = {
            "ok": False,
            "status": status,
            "elapsed_ms": 0,
            "message": "E_SIGN_BRIDGE_URL tanımlı değil — nitelikli e-imza köprüsü kapalı.",
        }
    else:
        try:
            with httpx.Client(timeout=3.0, follow_redirects=True) as client:
                try:
                    resp = client.head(url)
                    if resp.status_code == 405:
                        resp = client.get(url)
                except httpx.HTTPError:
                    resp = client.get(url)
            elapsed = int((time.perf_counter() - started) * 1000)
            ok = 200 <= resp.status_code < 500
            status = "ready" if ok else "unreachable"
            result = {
                "ok": ok,
                "status": status,
                "http_status": resp.status_code,
                "elapsed_ms": elapsed,
                "message": "Köprü yanıt verdi." if ok else "Köprü erişilemedi.",
            }
        except httpx.TimeoutException:
            status = "unreachable"
            result = {
                "ok": False,
                "status": status,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "message": "Köprü zaman aşımı.",
            }
        except Exception as exc:
            status = "error"
            result = {
                "ok": False,
                "status": status,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "message": f"Köprü hatası: {type(exc).__name__}",
            }

    user.e_signature_bridge_status = result["status"]
    user.e_signature_bridge_checked_at = datetime.utcnow()
    if db is not None:
        db.add(user)
        db.flush()
    return {**result, "checked_at": user.e_signature_bridge_checked_at}


def draw_signature_image(canvas_obj, *, image_bytes: bytes, x: float, y: float, max_w: float, max_h: float) -> bool:
    """ReportLab canvas üzerine imza görseli yerleştir. Başarısızsa False."""
    try:
        from reportlab.lib.utils import ImageReader

        img = ImageReader(BytesIO(image_bytes))
        iw, ih = img.getSize()
        if iw <= 0 or ih <= 0:
            return False
        scale = min(max_w / float(iw), max_h / float(ih), 1.0)
        w, h = iw * scale, ih * scale
        canvas_obj.drawImage(img, x + (max_w - w) / 2, y, width=w, height=h, mask="auto", preserveAspectRatio=True)
        return True
    except Exception:
        return False
