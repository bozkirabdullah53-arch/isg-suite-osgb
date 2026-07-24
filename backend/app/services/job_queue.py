"""Hafif async iş kuyruğu (P1-10).

- Flag kapalı → senkron
- Flag açık + bellek → in-process thread
- Flag açık + REDIS_URL → Redis listesi + durum hash (çoklu instance durum paylaşır)
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

_HANDLERS: dict[str, Callable[..., Any]] = {}


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


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
_queue: deque[tuple[str, tuple, dict]] = deque()
_lock = threading.Lock()
_worker_started = False


def async_jobs_enabled() -> bool:
    return bool(getattr(settings, "async_jobs_enabled", False))


def register_handler(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    _HANDLERS[name] = fn
    return fn


def _redis():
    url = (getattr(settings, "redis_url", None) or "").strip()
    if not url:
        return None
    try:
        import redis

        return redis.from_url(url, decode_responses=True, socket_connect_timeout=1.5)
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
        r.expire(f"isg:job:{rec.id}", 86400)
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


def _run_job(job_id: str, name: str, args: tuple, kwargs: dict) -> None:
    rec = _jobs.get(job_id)
    if not rec:
        rec = JobRecord(id=job_id, name=name)
        with _lock:
            _jobs[job_id] = rec
    rec.status = JobStatus.RUNNING
    _persist(rec)
    fn = _HANDLERS.get(name)
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


def _worker_loop() -> None:
    r = _redis()
    while True:
        item = None
        if r is not None:
            try:
                popped = r.brpop("isg:jobs", timeout=1)
                if popped:
                    _, raw = popped
                    payload = json.loads(raw)
                    item = (
                        payload["id"],
                        payload["name"],
                        tuple(payload.get("args") or []),
                        dict(payload.get("kwargs") or {}),
                    )
            except Exception:
                logger.exception("Redis BRPOP failed; falling back to memory queue")
                r = None
        if item is None:
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
    if r is not None:
        try:
            # JSON-serializable args only for Redis path
            r.lpush(
                "isg:jobs",
                json.dumps({"id": job_id, "name": name, "args": list(args), "kwargs": kwargs}, default=str),
            )
            return rec
        except Exception:
            logger.exception("Redis LPUSH failed; using memory queue")
    with _lock:
        _queue.append((job_id, name, args, kwargs))
    return rec


def job_backend_label() -> str:
    if not async_jobs_enabled():
        return "off-sync-fallback"
    if _redis() is not None:
        return "on-redis"
    return "on-memory"
