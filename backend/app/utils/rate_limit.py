"""
Rate limiting (Section 29).

This is an in-memory sliding-window limiter, intentionally simple for a
single-process dev/demo deployment. In production (multiple Uvicorn/Gunicorn
workers or multiple pods) this MUST be backed by Redis (already a required
dependency for Celery) so limits are shared across processes -- swapping
the storage backend here is a self-contained change since callers only see
`is_rate_limited(key, max_calls, window_seconds)`.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)


def is_rate_limited(key: str, max_calls: int, window_seconds: int) -> bool:
    now = time.time()
    with _lock:
        window = _hits[key]
        while window and now - window[0] > window_seconds:
            window.popleft()
        if len(window) >= max_calls:
            return True
        window.append(now)
        return False
