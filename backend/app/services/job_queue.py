"""Hafif async iş kuyruğu (P1-10).

- Flag kapalı → senkron
- Flag açık + bellek → in-process thread
- Flag açık + REDIS_URL → Redis pending/processing + lease + durum hash

Redis v2 teslim güvenliği:
- İş BRPOPLPUSH ile processing listesine alınır; çalışmadan önce kaybolmaz.
- Worker heartbeat ile lease yeniler.
- Worker çökerse süresi dolan processing işi tekrar pending kuyruğuna alınır.
- DONE/FAILED işler tekrar yürütülmez.
- Top-level handler'lar modül yolu üzerinden başka process'te yeniden çözülebilir.
"""
from __future__ import annotations

import importlib
import json
import logging
import threading
import time as time_module
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

_HANDLERS: dict[str, Callable[..., Any]] = {}

_PENDING_KEY = "isg:jobs:v2:pending"
_PROCESSING_KEY = "isg:jobs:v2:processing"
_LEASES_KEY = "isg:jobs:v2:leases"
_LEGACY_PENDING_KEY = "isg:jobs"
_PAYLOAD_PREFIX = "isg:job:payload:"
_RUN_LOCK_PREFIX = "isg:job:runlock:"
_JOB_TTL_SEC = 86_400
_LEASE_SEC = 120
_HEARTBEAT_SEC = 30
_RECOVERY_INTERVAL_SEC = 15


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


_TERMINAL_STATUSES = {JobStatus.DONE, JobStatus.FAILED}


@dataclass
class JobRecord:
    id: str
    name: str
    status: JobStatus = JobStatus.QUEUED
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    result: Any = None


_jobs: dict[str, JobRecord] = {}
_queue: deque[tuple[str, str, tuple, dict]] = deque()
_lock = threading.Lock()
_worker_started = False


def async_jobs_enabled() -> bool:
    """P1-10: ASYNC_JOBS_ENABLED veya REDIS_URL → on.

    ASYNC_JOBS_FORCE_OFF Redis varken artık no-op (0.9.213 cutover);
    Redis yokken force_off hâlâ senkron tutar.
    """
    has_redis = bool((getattr(settings, "redis_url", None) or "").strip())
    if bool(getattr(settings, "async_jobs_enabled", False)):
        return True
    if has_redis:
        return True
    if bool(getattr(settings, "async_jobs_force_off", False)):
        return False
    return False


def register_handler(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    _HANDLERS[name] = fn
    return fn


def _handler_reference(fn: Callable[..., Any]) -> str | None:
    """Return importable module:qualname; closures/lambdas stay process-local."""
    module = getattr(fn, "__module__", "") or ""
    qualname = getattr(fn, "__qualname__", "") or ""
    if not module or not qualname or "<locals>" in qualname or "<lambda>" in qualname:
        return None
    return f"{module}:{qualname}"


def _resolve_handler(name: str, handler_ref: str | None) -> Callable[..., Any] | None:
    fn = _HANDLERS.get(name)
    if fn is not None:
        return fn
    if not handler_ref or ":" not in handler_ref:
        return None
    module_name, qualname = handler_ref.split(":", 1)
    if not module_name or not qualname or "<locals>" in qualname:
        return None
    try:
        obj: Any = importlib.import_module(module_name)
        for part in qualname.split("."):
            obj = getattr(obj, part)
        if callable(obj):
            _HANDLERS[name] = obj
            return obj
    except Exception:
        logger.exception("Job handler resolve failed: %s", handler_ref)
    return None


def _redis():
    url = (getattr(settings, "redis_url", None) or "").strip()
    if not url:
        return None
    try:
        import redis

        return redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=3,
        )
    except Exception:
        logger.exception("Redis job backend unavailable")
        return None


def _persist(rec: JobRecord) -> None:
    r = _redis()
    if not r:
        return
    try:
        payload = {
            "id": rec.id,
            "name": rec.name,
            "status": rec.status.value,
            "error": rec.error or "",
            "created_at": rec.created_at.isoformat() + "Z",
            "finished_at": rec.finished_at.isoformat() + "Z" if rec.finished_at else "",
            "result": json.dumps(rec.result, default=str) if rec.result is not None else "",
        }
        r.hset(f"isg:job:{rec.id}", mapping=payload)
        r.expire(f"isg:job:{rec.id}", _JOB_TTL_SEC)
    except Exception:
        logger.exception("Redis job persist failed")


def get_job(job_id: str) -> JobRecord | None:
    with _lock:
        if job_id in _jobs:
            return _jobs[job_id]
    r = _redis()
    if not r:
        return None
    try:
        data = r.hgetall(f"isg:job:{job_id}")
        if not data:
            return None
        rec = JobRecord(
            id=data.get("id") or job_id,
            name=data.get("name") or "",
            status=JobStatus(data.get("status") or "queued"),
            error=(data.get("error") or None) or None,
        )
        if data.get("created_at"):
            try:
                rec.created_at = datetime.fromisoformat(data["created_at"].replace("Z", ""))
            except ValueError:
                pass
        if data.get("finished_at"):
            try:
                rec.finished_at = datetime.fromisoformat(data["finished_at"].replace("Z", ""))
            except ValueError:
                pass
        if data.get("result"):
            try:
                rec.result = json.loads(data["result"])
            except json.JSONDecodeError:
                rec.result = data["result"]
        with _lock:
            _jobs[job_id] = rec
        return rec
    except Exception:
        logger.exception("Redis job get failed")
        return None


def _run_job(
    job_id: str,
    name: str,
    args: tuple,
    kwargs: dict,
    *,
    handler_ref: str | None = None,
) -> None:
    rec = _jobs.get(job_id)
    if not rec:
        rec = get_job(job_id)
    if not rec:
        rec = JobRecord(id=job_id, name=name)
        with _lock:
            _jobs[job_id] = rec
    if rec.status in _TERMINAL_STATUSES:
        return

    rec.status = JobStatus.RUNNING
    rec.error = None
    _persist(rec)
    fn = _resolve_handler(name, handler_ref)
    try:
        if not fn:
            raise RuntimeError(f"İşleyici yok: {name}")
        rec.result = fn(*args, **kwargs)
        rec.status = JobStatus.DONE
    except Exception as exc:
        logger.exception("Job failed: %s", job_id)
        rec.status = JobStatus.FAILED
        rec.error = str(exc)[:500]
    finally:
        rec.finished_at = datetime.utcnow()
        _persist(rec)


def _release_run_lock(r, job_id: str, token: str) -> None:
    key = f"{_RUN_LOCK_PREFIX}{job_id}"
    try:
        if r.get(key) == token:
            r.delete(key)
    except Exception:
        logger.exception("Redis job lock release failed: %s", job_id)


def _ack_redis_job(r, job_id: str, *, token: str | None = None) -> None:
    try:
        r.lrem(_PROCESSING_KEY, 1, job_id)
        r.zrem(_LEASES_KEY, job_id)
        r.delete(f"{_PAYLOAD_PREFIX}{job_id}")
        if token:
            _release_run_lock(r, job_id, token)
    except Exception:
        logger.exception("Redis job ack failed: %s", job_id)


def _lease_heartbeat(r, job_id: str, token: str, stop: threading.Event) -> None:
    key = f"{_RUN_LOCK_PREFIX}{job_id}"
    while not stop.wait(_HEARTBEAT_SEC):
        try:
            if r.get(key) != token:
                return
            r.expire(key, _LEASE_SEC)
            r.zadd(_LEASES_KEY, {job_id: time_module.time() + _LEASE_SEC})
        except Exception:
            logger.exception("Redis job heartbeat failed: %s", job_id)
            return


def _recover_expired_jobs(r, *, now: float | None = None) -> int:
    """Move expired processing jobs back to pending when no run lock remains."""
    current = time_module.time() if now is None else now
    recovered = 0
    try:
        expired = list(r.zrangebyscore(_LEASES_KEY, "-inf", current) or [])
        for job_id in expired:
            if r.exists(f"{_RUN_LOCK_PREFIX}{job_id}"):
                continue
            removed = int(r.lrem(_PROCESSING_KEY, 1, job_id) or 0)
            if removed:
                r.lpush(_PENDING_KEY, job_id)
                recovered += 1
            r.zrem(_LEASES_KEY, job_id)
        if recovered:
            logger.warning("Recovered %s expired Redis jobs", recovered)
    except Exception:
        logger.exception("Redis expired job recovery failed")
    return recovered


def _load_redis_payload(r, job_id: str) -> dict[str, Any] | None:
    raw = r.get(f"{_PAYLOAD_PREFIX}{job_id}")
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        return None


def _run_claimed_redis_job(r, job_id: str) -> None:
    rec = get_job(job_id)
    if rec and rec.status in _TERMINAL_STATUSES:
        _ack_redis_job(r, job_id)
        return

    payload = _load_redis_payload(r, job_id)
    if not payload:
        rec = rec or JobRecord(id=job_id, name="unknown")
        rec.status = JobStatus.FAILED
        rec.error = "İş payload kaydı bulunamadı veya bozuk."
        rec.finished_at = datetime.utcnow()
        with _lock:
            _jobs[job_id] = rec
        _persist(rec)
        _ack_redis_job(r, job_id)
        return

    token = uuid.uuid4().hex
    lock_key = f"{_RUN_LOCK_PREFIX}{job_id}"
    if not r.set(lock_key, token, nx=True, ex=_LEASE_SEC):
        # Başka worker işi yürütüyor; bu yinelenen claim'i temizle.
        try:
            r.lrem(_PROCESSING_KEY, 1, job_id)
        except Exception:
            logger.exception("Duplicate job claim cleanup failed: %s", job_id)
        return

    r.zadd(_LEASES_KEY, {job_id: time_module.time() + _LEASE_SEC})
    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_lease_heartbeat,
        args=(r, job_id, token, stop),
        name=f"isg-job-heartbeat-{job_id[:8]}",
        daemon=True,
    )
    heartbeat.start()
    try:
        _run_job(
            job_id,
            str(payload.get("name") or ""),
            tuple(payload.get("args") or []),
            dict(payload.get("kwargs") or {}),
            handler_ref=(payload.get("handler") or None),
        )
    finally:
        stop.set()
        _ack_redis_job(r, job_id, token=token)


def _consume_legacy_job(r) -> bool:
    """Best-effort compatibility for queue entries created before v2."""
    popped = r.rpop(_LEGACY_PENDING_KEY)
    if not popped:
        return False
    try:
        payload = json.loads(popped)
        job_id = str(payload["id"])
        handler_ref = payload.get("handler")
        if not handler_ref:
            handler_ref = _handler_reference(_HANDLERS.get(str(payload.get("name") or ""))) if _HANDLERS.get(str(payload.get("name") or "")) else None
        _run_job(
            job_id,
            str(payload.get("name") or ""),
            tuple(payload.get("args") or []),
            dict(payload.get("kwargs") or {}),
            handler_ref=handler_ref,
        )
    except Exception:
        logger.exception("Legacy Redis job could not be processed")
    return True


def _worker_loop() -> None:
    r = _redis()
    last_recovery = 0.0
    last_reconnect = 0.0
    while True:
        item = None
        now = time_module.time()
        if r is None and now - last_reconnect >= 5:
            r = _redis()
            last_reconnect = now
        if r is not None:
            try:
                if now - last_recovery >= _RECOVERY_INTERVAL_SEC:
                    _recover_expired_jobs(r, now=now)
                    last_recovery = now
                job_id = r.brpoplpush(_PENDING_KEY, _PROCESSING_KEY, timeout=1)
                if job_id:
                    _run_claimed_redis_job(r, str(job_id))
                    continue
                if _consume_legacy_job(r):
                    continue
            except Exception:
                logger.exception("Redis job worker failed; falling back to memory queue")
                r = None
        with _lock:
            if _queue:
                item = _queue.popleft()
        if item is None:
            threading.Event().wait(0.3)
            continue
        job_id, name, args, kwargs = item
        _run_job(job_id, name, args, kwargs)


def _ensure_worker() -> None:
    global _worker_started
    with _lock:
        if _worker_started:
            return
        t = threading.Thread(target=_worker_loop, name="isg-job-worker", daemon=True)
        t.start()
        _worker_started = True


def _enqueue_redis(r, rec: JobRecord, name: str, fn: Callable[..., Any], args: tuple, kwargs: dict) -> bool:
    handler_ref = _handler_reference(fn)
    if not handler_ref:
        logger.warning("Job handler is not importable; using process-local queue: %s", name)
        return False
    payload = json.dumps(
        {
            "id": rec.id,
            "name": name,
            "handler": handler_ref,
            "args": list(args),
            "kwargs": kwargs,
        },
        default=str,
    )
    try:
        r.set(f"{_PAYLOAD_PREFIX}{rec.id}", payload, ex=_JOB_TTL_SEC)
        r.lpush(_PENDING_KEY, rec.id)
        return True
    except Exception:
        logger.exception("Redis job enqueue failed; using memory queue")
        try:
            r.delete(f"{_PAYLOAD_PREFIX}{rec.id}")
        except Exception:
            pass
        return False


def enqueue(name: str, fn: Callable[..., Any], *args, **kwargs) -> JobRecord:
    """İş kuyruğa alır. Flag kapalıysa hemen çalıştırır."""
    register_handler(name, fn)
    job_id = uuid.uuid4().hex
    rec = JobRecord(id=job_id, name=name)
    with _lock:
        _jobs[job_id] = rec
    _persist(rec)
    if not async_jobs_enabled():
        _run_job(job_id, name, args, kwargs)
        return rec
    _ensure_worker()
    r = _redis()
    if r is not None and _enqueue_redis(r, rec, name, fn, args, kwargs):
        return rec
    with _lock:
        _queue.append((job_id, name, args, kwargs))
    return rec


def job_backend_label() -> str:
    if not async_jobs_enabled():
        return "off-sync-fallback"
    if _redis() is not None:
        return "on-redis-leased-v2"
    return "on-memory"
