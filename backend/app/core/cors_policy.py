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


def build_cors_origins(
    *,
    environment: str | None,
    frontend_origin: str | None,
) -> list[str]:
    """Return an ordered, deduplicated origin allowlist for the environment."""
    origins: list[str | None] = [frontend_origin, *APPROVED_PRODUCTION_ORIGINS]
    if not is_production_environment(environment):
        origins.extend(LOCAL_DEVELOPMENT_ORIGINS)

    return list(dict.fromkeys(origin.strip() for origin in origins if origin and origin.strip()))
