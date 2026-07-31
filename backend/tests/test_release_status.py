"""Public /health slim + infra-detail payload."""
from app.services import release_status as rs


def test_public_health_is_minimal():
    body = rs.public_health_payload()
    assert set(body.keys()) == {"status", "service", "version", "environment"}
    assert body["status"] == "ok"
    assert "health_field_encryption_key" not in body
    assert "infra_cutover_remaining" not in body


def test_infra_detail_has_crypto_and_gaps():
    body = rs.infra_detail_payload()
    assert body["status"] == "ok"
    assert "health_field_encryption_key" in body
    assert "infra_cutover_remaining" in body
    assert "infra_cutover_optional" in body
    assert "hardening_complete" in body
    assert "infra_cutover_steps" in body
    assert isinstance(body["infra_cutover_steps"], list)
    assert body.get("public_health") == "slim-v1"


def test_public_health_endpoint_exposes_no_feature_flags():
    """Uç nokta seviyesinde de sızıntı olmamalı (recon yüzeyi)."""
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"status", "service", "version", "environment"}


def test_infra_detail_endpoint_requires_auth():
    """Bayrak kaydı yalnızca yetkili istekle görülebilir."""
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).get("/api/v1/system/infra-detail")
    assert r.status_code in (401, 403)
