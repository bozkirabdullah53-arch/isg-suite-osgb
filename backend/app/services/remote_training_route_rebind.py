"""Rebuild FastAPI route handlers after approved remote-training overrides.

Changing only ``APIRoute.endpoint`` is not sufficient: FastAPI builds a
``Dependant`` graph and Starlette ASGI handler when the route is registered.
This guard rebinds both the dependant callable and the request handler while the
router is still private to ``app.api.remote_training`` (before main includes it
into the application). The endpoint signatures are intentionally identical to
the original publish/delete handlers, so path and dependency contracts remain
unchanged.
"""
from __future__ import annotations

from typing import Any, Callable

from starlette.routing import request_response

from app.api import remote_training as remote_api
from app.services.remote_training_live_video_sync import (
    delete_catalog_video_live,
    publish_catalog_video_live,
)

_INSTALLED = False


def _rebind(path_suffix: str, method: str, endpoint: Callable[..., Any]) -> bool:
    method = method.upper()
    for route in remote_api.router.routes:
        route_path = str(getattr(route, "path", "") or "")
        methods = set(getattr(route, "methods", set()) or set())
        if not route_path.endswith(path_suffix) or method not in methods:
            continue

        route.endpoint = endpoint
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            raise RuntimeError(f"FastAPI dependant bulunamadı: {method} {route_path}")
        dependant.call = endpoint

        get_route_handler = getattr(route, "get_route_handler", None)
        if not callable(get_route_handler):
            raise RuntimeError(f"FastAPI route handler yeniden kurulamadı: {method} {route_path}")
        route.app = request_response(get_route_handler())
        return True
    return False


def install_remote_training_route_rebind() -> dict[str, Any]:
    global _INSTALLED
    if _INSTALLED:
        return {"installed": True, "already_installed": True}

    publish = _rebind(
        "/catalog/videos/{video_id}/publish",
        "POST",
        publish_catalog_video_live,
    )
    delete = _rebind(
        "/catalog/videos/{video_id}",
        "DELETE",
        delete_catalog_video_live,
    )
    if not publish or not delete:
        raise RuntimeError("Uzaktan eğitim canlı video route handler'ları yeniden bağlanamadı.")

    _INSTALLED = True
    return {
        "installed": True,
        "already_installed": False,
        "publish_rebound": publish,
        "delete_rebound": delete,
    }
