"""Environment-aware CORS origin policy.

Production accepts only explicitly approved HTTPS frontends. Local development
origins remain available outside production so existing developer workflows are
preserved.
"""
from __future__ import annotations

from urllib.parse import urlsplit


PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod", "live"})
APPROVED_PRODUCTION_ORIGINS = (
    "https://isg-suite-web-1u9t.onrender.com",
    "https://www.isgsuite.tr",
    "https://isgsuite.tr",
    "https://www.isgsuite.com.tr",
    "https://isgsuite.com.tr",
    "https://idea-isg-web.onrender.com",
)
LOCAL_DEVELOPMENT_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def is_production_environment(environment: str | None) -> bool:
    return (environment or "").strip().lower() in PRODUCTION_ENVIRONMENTS


def build_cors_origins(
    *,
    environment: str | None,
    frontend_origin: str | None,
) -> list[str]:
    """Return an ordered, deduplicated origin allowlist for the environment."""
    production = is_production_environment(environment)
    origins: list[str | None] = [frontend_origin, *APPROVED_PRODUCTION_ORIGINS]
    if not production:
        origins.extend(LOCAL_DEVELOPMENT_ORIGINS)

    normalized: list[str] = []
    for raw in origins:
        value = (raw or "").strip()
        if not value:
            continue
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or (production and parsed.scheme != "https")
        ):
            continue
        normalized.append(f"{parsed.scheme}://{parsed.netloc}")
    return list(dict.fromkeys(normalized))
