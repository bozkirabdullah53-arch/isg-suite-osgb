"""Job queue + Redis label smoke."""
from app.services.job_queue import JobStatus, enqueue, get_job, job_backend_label


def test_enqueue_sync_when_flag_off(monkeypatch):
    monkeypatch.setattr("app.services.job_queue.async_jobs_enabled", lambda: False)

    def work(x):
        return x * 2

    rec = enqueue("double", work, 21)
    assert rec.status == JobStatus.DONE
    assert rec.result == 42
    assert get_job(rec.id) is rec


def test_job_backend_label_sync(monkeypatch):
    monkeypatch.setattr("app.services.job_queue.async_jobs_enabled", lambda: False)
    assert job_backend_label() == "off-sync-fallback"


def test_system_job_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr("app.services.job_queue.async_jobs_enabled", lambda: False)
    from app.main import app

    rec = enqueue("ping", lambda: "ok")
    client = TestClient(app)
    r = client.get(f"/api/v1/system/jobs/{rec.id}")
    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert client.get("/api/v1/system/jobs/missing").status_code == 404
