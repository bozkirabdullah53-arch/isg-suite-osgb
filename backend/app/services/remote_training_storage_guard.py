"""Resilient storage selection for large remote-training videos.

Credentials alone do not prove that R2/S3 is reachable. Production may legally
continue on the persistent Render disk when remote mirroring is optional, so a
remote-training upload must not select a known-unreachable S3 client merely
because environment variables are present.

This module wraps only the remote-training store factory. Other application
storage behavior is unchanged. The guard is idempotent and fail-closed whenever
OBJECT_STORAGE_REMOTE_REQUIRED=true.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.api import remote_training as remote_api
from app.core.config import settings
from app.services.object_store import (
    LocalObjectStore,
    get_object_store,
    get_remote_object_store,
    probe_object_storage,
    remote_mirror_required,
    remote_object_storage_credentials_ok,
)

logger = logging.getLogger(__name__)
_INSTALLED = False
_PROBE_TTL_SECONDS = 60.0
_probe_checked_at = 0.0
_probe_reachable: bool | None = None
_fallback_active = False


def _backend() -> str:
    return str(getattr(settings, "object_storage_backend", "local") or "local").strip().lower()


def _fallback_store():
    backend = _backend()
    # local and dual already provide a durable/local compatibility path. A
    # direct s3/r2 backend has no local fallback, so construct the same safe
    # upload_dir-backed store used before cutover when remote is optional.
    if backend in {"local", "disk", "fs", "dual"}:
        return get_object_store()
    return LocalObjectStore()


def _remote_reachable(*, force_probe: bool = False) -> bool:
    global _probe_checked_at, _probe_reachable
    if not remote_object_storage_credentials_ok():
        _probe_reachable = False
        _probe_checked_at = time.monotonic()
        return False

    now = time.monotonic()
    if (
        not force_probe
        and _probe_reachable is not None
        and now - _probe_checked_at < _PROBE_TTL_SECONDS
    ):
        return bool(_probe_reachable)

    result = probe_object_storage()
    _probe_reachable = result.get("status") == "reachable"
    _probe_checked_at = now
    return bool(_probe_reachable)


def remote_training_storage_guard_status() -> dict[str, Any]:
    """Return a recon-safe status snapshot without performing network I/O."""
    credentials = remote_object_storage_credentials_ok()
    if not credentials:
        probe_state = "not_configured"
    elif _probe_checked_at <= 0 or _probe_reachable is None:
        probe_state = "unknown"
    else:
        probe_state = "reachable" if _probe_reachable else "unreachable"
    return {
        "backend": _backend(),
        "remote_required": remote_mirror_required(),
        "credentials_configured": credentials,
        "probe_state": probe_state,
        "fallback_active": bool(_fallback_active),
    }


def resilient_remote_training_video_store():
    """Return remote storage only when it is currently usable.

    Optional remote outage => persistent/local compatibility path.
    Required remote outage => fail closed before accepting a video mutation.
    """
    global _fallback_active
    if bool(getattr(settings, "object_storage_force_local", False)):
        if remote_mirror_required():
            raise RuntimeError("Uzak depolama zorunluyken force-local kullanılamaz.")
        _fallback_active = True
        return _fallback_store()

    if not remote_object_storage_credentials_ok():
        if remote_mirror_required():
            raise RuntimeError("Zorunlu uzak video depolama credential bilgileri eksik.")
        _fallback_active = False
        return _fallback_store()

    if _remote_reachable():
        remote = get_remote_object_store()
        if remote is not None:
            _fallback_active = False
            return remote

    if remote_mirror_required():
        _fallback_active = False
        raise RuntimeError("Zorunlu uzak video depolama şu anda erişilemiyor.")

    _fallback_active = True
    logger.warning(
        "Remote-training video store fallback active: backend=%s; remote probe unreachable",
        _backend(),
    )
    return _fallback_store()


def install_remote_training_storage_guard() -> dict[str, Any]:
    """Install the resolver before FastAPI begins serving remote-training routes."""
    global _INSTALLED
    current = remote_api._remote_training_video_store
    if _INSTALLED or getattr(current, "_resilient_remote_training_storage_guard", False):
        _INSTALLED = True
        return {"installed": True, "already_installed": True}

    resilient_remote_training_video_store._resilient_remote_training_storage_guard = True
    remote_api._remote_training_video_store = resilient_remote_training_video_store
    _INSTALLED = True
    return {"installed": True, "already_installed": False}


def reset_remote_training_storage_guard_for_tests() -> None:
    global _fallback_active, _probe_checked_at, _probe_reachable
    _fallback_active = False
    _probe_checked_at = 0.0
    _probe_reachable = None