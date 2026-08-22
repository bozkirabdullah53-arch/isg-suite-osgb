"""Job queue + Redis teslim güvenliği smoke."""
from __future__ import annotations

import json

from app.services import job_queue as jq
from app.services.job_queue import JobRecord, JobStatus, enqueue, get_job, job_backend_label


def importable_job_handler(value: int) -> int:
    return value + 1


class _FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.hashes: dict[str, dict] = {}
        self.lists: dict[str, list[str]] = {}
        self.zsets: dict[str, dict[str, float]] = {}
        self.locks: dict[str, str] = {}

    def hset(self, key, mapping):
        self.hashes[key] = dict(mapping)
        return 1

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def expire(self, key, seconds):
        _ = key, seconds
        return True

    def set(self, key, value, ex=None, nx=False):
        _ = ex
        if nx and key in self.locks:
            return False
        if nx:
            self.locks[key] = value
        else:
            self.values[key] = value
        return True

    def get(self, key):
        if key in self.locks:
            return self.locks[key]
        return self.values.get(key)

    def delete(self, key):
        self.values.pop(key, None)
        self.locks.pop(key, None)
        self.hashes.pop(key, None)
        return 1

    def exists(self, key):
        return int(key in self.locks or key in self.values or key in self.hashes)

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def lrem(self, key, count, value):
        rows = self.lists.setdefault(key, [])
        removed = 0
        kept = []
        for item in rows:
            if item == value and removed < count:
                removed += 1
            else:
                kept.append(item)
        self.lists[key] = kept
        return removed

    def zadd(self, key, mapping):
        self.zsets.setdefault(key, {}).update(mapping)
        return len(mapping)

    def zrem(self, key, value):
        return int(self.zsets.setdefault(key, {}).pop(value, None) is not None)

    def zrangebyscore(self, key, minimum, maximum):
        _ = minimum
        return [
            member
            for member, score in self.zsets.setdefault(key, {}).items()
            if score <= float(maximum)
        ]


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
    from app.api.deps import get_current_user

    rec = enqueue("ping", lambda: "ok")
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: object()
    try:
        r = client.get(f"/api/v1/system/jobs/{rec.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "done"
        assert client.get("/api/v1/system/jobs/missing").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_redis_enqueue_persists_importable_handler_reference(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(jq, "async_jobs_enabled", lambda: True)
    monkeypatch.setattr(jq, "_ensure_worker", lambda: None)
    monkeypatch.setattr(jq, "_redis", lambda: fake)
    monkeypatch.setattr(jq, "_persist", lambda rec: None)

    rec = jq.enqueue("importable", importable_job_handler, 7)

    assert fake.lists[jq._PENDING_KEY] == [rec.id]
    payload = json.loads(fake.values[f"{jq._PAYLOAD_PREFIX}{rec.id}"])
    assert payload["handler"].endswith(":importable_job_handler")
    assert payload["args"] == [7]


def test_expired_processing_job_is_requeued(monkeypatch):
    fake = _FakeRedis()
    job_id = "expired-job"
    fake.lists[jq._PROCESSING_KEY] = [job_id]
    fake.zsets[jq._LEASES_KEY] = {job_id: 10.0}

    recovered = jq._recover_expired_jobs(fake, now=20.0)

    assert recovered == 1
    assert fake.lists[jq._PROCESSING_KEY] == []
    assert fake.lists[jq._PENDING_KEY] == [job_id]
    assert job_id not in fake.zsets[jq._LEASES_KEY]


def test_terminal_job_duplicate_claim_is_acked_without_rerun(monkeypatch):
    fake = _FakeRedis()
    job_id = "done-job"
    fake.lists[jq._PROCESSING_KEY] = [job_id]
    fake.zsets[jq._LEASES_KEY] = {job_id: 999.0}
    fake.values[f"{jq._PAYLOAD_PREFIX}{job_id}"] = json.dumps(
        {
            "id": job_id,
            "name": "importable",
            "handler": f"{__name__}:importable_job_handler",
            "args": [1],
            "kwargs": {},
        }
    )
    rec = JobRecord(id=job_id, name="importable", status=JobStatus.DONE, result=2)
    monkeypatch.setitem(jq._jobs, job_id, rec)

    jq._run_claimed_redis_job(fake, job_id)

    assert fake.lists[jq._PROCESSING_KEY] == []
    assert f"{jq._PAYLOAD_PREFIX}{job_id}" not in fake.values
    assert rec.result == 2
