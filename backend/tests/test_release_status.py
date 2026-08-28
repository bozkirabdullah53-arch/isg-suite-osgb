"""Public /health slim + infra-detail payload."""
from app.services import release_status as rs


def test_public_health_is_minimal():
    body = rs.public_health_payload()
    # Sürüm/environment herkese açıktan kaldırıldı (smoke test B3 bulgusu).
    # Yalnızca status ve service kalır — recon yüzeyi en aza indirildi.
    assert set(body.keys()) == {"status", "service"}
    assert body["status"] in {"ok", "degraded"}
    assert "version" not in body
    assert "environment" not in body
    assert "health_field_encryption_key" not in body
    assert "infra_cutover_remaining" not in body


def test_public_health_marks_known_optional_remote_video_outage_degraded(monkeypatch):
    from app.services import remote_training_storage_guard as guard

    monkeypatch.setattr(
        guard,
        "remote_training_storage_guard_status",
        lambda: {
            "backend": "local",
            "remote_required": False,
            "credentials_configured": True,
            "probe_state": "unreachable",
            "fallback_active": True,
        },
    )
    assert rs.public_health_payload()["status"] == "degraded"


def test_infra_detail_has_crypto_and_gaps():
    body = rs.infra_detail_payload()
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body
    assert "health_field_encryption_key" in body
    assert "infra_cutover_remaining" in body
    assert "infra_cutover_optional" in body
    assert "hardening_complete" in body
    assert "infra_cutover_steps" in body
    assert "remote_training_video_storage" in body
    assert isinstance(body["remote_training_video_storage"], dict)
    assert isinstance(body["infra_cutover_steps"], list)
    assert body.get("public_health") == "slim-v2-degraded-aware"


def test_public_health_endpoint_exposes_no_feature_flags():
    """Uç nokta seviyesinde de sızıntı olmamalı (recon yüzeyi)."""
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).get("/health")
    assert r.status_code == 200
    # version/environment artık public /health'te yok
    assert set(r.json().keys()) == {"status", "service"}
    assert r.json()["status"] in {"ok", "degraded"}


def test_infra_detail_endpoint_requires_auth():
    """Bayrak kaydı yalnızca yetkili istekle görülebilir."""
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).get("/api/v1/system/infra-detail")
    assert r.status_code in (401, 403)


def test_system_health_and_job_status_require_auth():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/api/v1/system/health").status_code in (401, 403)
    assert client.get("/api/v1/system/jobs/not-a-real-job").status_code in (401, 403)