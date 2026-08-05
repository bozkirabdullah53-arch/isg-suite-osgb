"""İBYS başvuru rotaları için anonim dış yetkilendirme smoke kanıtı üretir."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

SMOKE_VERSION = "ibys-external-auth-smoke-v1"
PROTECTED_PROBES: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("GET", "/api/v1/ibys-application/profile", None),
    ("GET", "/api/v1/ibys-application/readiness", None),
    (
        "POST",
        "/api/v1/ibys-application/preflight",
        {"company_profile": {}, "attachment_filenames": []},
    ),
)
ALLOWED_DENIAL_STATUSES = {401, 403}
FORBIDDEN_RESPONSE_MARKERS = (
    "application_preparation_percent",
    "official_registration_claim",
    "dataset_count",
    "required_demo_fields",
)


def normalize_base_url(value: str, *, allow_http_localhost: bool = False) -> str:
    """Hedefi normalize eder; credential, query ve fragment içeren URL'leri reddeder."""
    raw = str(value or "").strip()
    parts = urlsplit(raw)
    if parts.scheme not in {"https", "http"}:
        raise ValueError("base URL scheme must be https")
    if not parts.hostname:
        raise ValueError("base URL host is required")
    if parts.username or parts.password:
        raise ValueError("base URL must not contain credentials")
    if parts.query or parts.fragment:
        raise ValueError("base URL must not contain query or fragment")
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parts.scheme != "https" and not (allow_http_localhost and parts.hostname in local_hosts):
        raise ValueError("https is required for external smoke targets")
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _evidence_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def run_external_auth_smoke(
    base_url: str,
    *,
    timeout_s: float = 15.0,
    transport: httpx.BaseTransport | None = None,
    allow_http_localhost: bool = False,
) -> dict[str, Any]:
    """Korunan rotaların anonim isteğe veri vermediğini kanıtlar; body saklamaz."""
    target = normalize_base_url(base_url, allow_http_localhost=allow_http_localhost)
    checks: list[dict[str, Any]] = []
    with httpx.Client(
        timeout=timeout_s,
        follow_redirects=False,
        transport=transport,
        headers={"Accept": "application/json", "User-Agent": SMOKE_VERSION},
    ) as client:
        for method, path, body in PROTECTED_PROBES:
            started = time.perf_counter()
            try:
                response = client.request(method, target + path, json=body)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                response_text = response.text[:4096]
                leaked_markers = [marker for marker in FORBIDDEN_RESPONSE_MARKERS if marker in response_text]
                denied = response.status_code in ALLOWED_DENIAL_STATUSES
                checks.append(
                    {
                        "method": method,
                        "path": path,
                        "ok": denied and not leaked_markers,
                        "http_status": response.status_code,
                        "elapsed_ms": elapsed_ms,
                        "response_body_stored": False,
                        "leaked_markers": leaked_markers,
                    }
                )
            except httpx.TimeoutException:
                checks.append(
                    {
                        "method": method,
                        "path": path,
                        "ok": False,
                        "http_status": None,
                        "elapsed_ms": int((time.perf_counter() - started) * 1000),
                        "response_body_stored": False,
                        "error": "timeout",
                    }
                )
            except httpx.HTTPError:
                checks.append(
                    {
                        "method": method,
                        "path": path,
                        "ok": False,
                        "http_status": None,
                        "elapsed_ms": int((time.perf_counter() - started) * 1000),
                        "response_body_stored": False,
                        "error": "network_error",
                    }
                )

    evidence: dict[str, Any] = {
        "smoke_version": SMOKE_VERSION,
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "target_origin": target,
        "anonymous_only": True,
        "authorization_header_sent": False,
        "allowed_denial_statuses": sorted(ALLOWED_DENIAL_STATUSES),
        "checks": checks,
        "overall_ok": bool(checks) and all(check["ok"] for check in checks),
        "official_registration_claim": False,
    }
    evidence["evidence_sha256"] = _evidence_hash(evidence)
    return evidence


def verify_smoke_evidence_hash(evidence: dict[str, Any]) -> bool:
    supplied = str(evidence.get("evidence_sha256") or "")
    unsigned = {key: value for key, value in evidence.items() if key != "evidence_sha256"}
    return len(supplied) == 64 and supplied == _evidence_hash(unsigned)
