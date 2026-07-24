"""Hafif async iş kuyruğu iskeleti (P1-10) — varsayılan in-process; Redis/RQ sonrası adım.

Flag kapalıyken enqueue senkron çalıştırır (davranış değişmez).
"""
from __future__ import annotations

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
_queue: deque[tuple[str, Callable[..., Any], tuple, dict]] = deque()
_lock = threading.Lock()
_worker_started = False


def async_jobs_enabled() -> bool:
    return bool(getattr(settings, "async_jobs_enabled", False))


def get_job(job_id: str) -> JobRecord | None:
    return _jobs.get(job_id)


def _run_job(job_id: str, fn: Callable[..., Any], args: tuple, kwargs: dict) -> None:
    rec = _jobs.get(job_id)
    if not rec:
        return
    rec.status = JobStatus.RUNNING
    try:
        rec.result = fn(*args, **kwargs)
        rec.status = JobStatus.DONE
    except Exception as exc:
        logger.exception("Job failed: %s", job_id)
        rec.status = JobStatus.FAILED
        rec.error = str(exc)[:500]
    finally:
        rec.finished_at = datetime.utcnow()


def _worker_loop() -> None:
    while True:
        item = None
        with _lock:
            if _queue:
                item = _queue.popleft()
        if item is None:
            threading.Event().wait(0.5)
            continue
        job_id, fn, args, kwargs = item
        _run_job(job_id, fn, args, kwargs)


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
    job_id = uuid.uuid4().hex
    rec = JobRecord(id=job_id, name=name)
    with _lock:
        _jobs[job_id] = rec
    if not async_jobs_enabled():
        _run_job(job_id, fn, args, kwargs)
        return rec
    _ensure_worker()
    with _lock:
        _queue.append((job_id, fn, args, kwargs))
    return rec
