from __future__ import annotations

import httpx
import pytest

from app.services.ibys_external_auth_smoke import (
    PROTECTED_PROBES,
    normalize_base_url,
    run_external_auth_smoke,
    verify_smoke_evidence_hash,
)


def test_external_smoke_accepts_only_https_without_embedded_credentials():
    assert normalize_base_url("https://example.com/") == "https://example.com"

    with pytest.raises(ValueError, match="https"):
        normalize_base_url("http://example.com")
    with pytest.raises(ValueError, match="credentials"):
        normalize_base_url("https://user:secret@example.com")
    with pytest.raises(ValueError, match="query or fragment"):
        normalize_base_url("https://example.com?token=secret")


def test_external_smoke_all_protected_routes_denied_and_evidence_hash_valid():
    requested: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        return httpx.Response(401, json={"detail": "Kimlik doğrulama gerekli"})

    evidence = run_external_auth_smoke(
        "https://staging.example.com",
        transport=httpx.MockTransport(handler),
    )

    assert evidence["overall_ok"] is True
    assert evidence["anonymous_only"] is True
    assert evidence["authorization_header_sent"] is False
    assert len(evidence["checks"]) == len(PROTECTED_PROBES)
    assert all(check["http_status"] == 401 for check in evidence["checks"])
    assert all(check["response_body_stored"] is False for check in evidence["checks"])
    assert verify_smoke_evidence_hash(evidence) is True
    assert all("authorization" not in request.headers for request in requested)


def test_external_smoke_fails_when_protected_route_returns_data_marker():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"dataset_count": 12})
        return httpx.Response(403, json={"detail": "forbidden"})

    evidence = run_external_auth_smoke(
        "https://staging.example.com",
        transport=httpx.MockTransport(handler),
    )

    assert evidence["overall_ok"] is False
    profile_check = next(check for check in evidence["checks"] if check["path"].endswith("/profile"))
    assert profile_check["http_status"] == 200
    assert profile_check["ok"] is False
    assert profile_check["leaked_markers"] == ["dataset_count"]
    assert verify_smoke_evidence_hash(evidence) is True


def test_evidence_hash_detects_tampering():
    evidence = run_external_auth_smoke(
        "https://staging.example.com",
        transport=httpx.MockTransport(lambda request: httpx.Response(403)),
    )
    evidence["overall_ok"] = False

    assert verify_smoke_evidence_hash(evidence) is False
