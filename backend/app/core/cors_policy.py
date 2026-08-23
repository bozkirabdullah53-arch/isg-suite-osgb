"""Environment-aware CORS origin policy.

Production accepts only explicitly approved HTTPS frontends. Local development
origins remain available outside production so existing developer workflows are
preserved.
"""
from __future__ import annotations


PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod", "live"})
APPROVED_PRODUCTION_ORIGINS = (
    "https://isg-suite-web-1u9t.onrender.com",
    "https://www.isgsuite.tr",
    "https://isgsuite.tr",
)
LOCAL_DEVELOPMENT_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def is_production_environment(environment: str | None) -> bool:
    return (environment or "").strip().lower() in PRODUCTION_ENVIRONMENTS


def _split_configured_origins(value: str | None) -> list[str]:
    """Parse one or more comma-separated origins without changing old values."""
    return [
        origin.strip()
        for origin in (value or "").split(",")
        if origin and origin.strip()
    ]


def build_cors_origins(
    *,
    environment: str | None,
    frontend_origin: str | None,
    frontend_origins: str | None = None,
) -> list[str]:
    """Return an ordered, deduplicated origin allowlist for the environment."""
    configured_origins = [
        *_split_configured_origins(frontend_origin),
        *_split_configured_origins(frontend_origins),
    ]
    origins: list[str] = [*configured_origins, *APPROVED_PRODUCTION_ORIGINS]
    if not is_production_environment(environment):
        origins.extend(LOCAL_DEVELOPMENT_ORIGINS)

    return list(dict.fromkeys(origin.strip() for origin in origins if origin and origin.strip()))
