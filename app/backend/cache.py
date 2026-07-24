"""Tiny TTL cache decorator for cheap, slow-changing reference reads.

Used for /api/config, segments, products — never for per-customer payloads
(cardinality explosion). Thread-safe enough for the app's threadpool endpoints.
"""
from __future__ import annotations

import threading
import time
from functools import wraps
from typing import Any, Callable

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def ttl_cached(ttl: int = 300) -> Callable:
    """Cache a zero-arg (or hashable-arg) function's result for ``ttl`` seconds."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = f"{fn.__module__}.{fn.__qualname__}:{args}:{sorted(kwargs.items())}"
            now = time.monotonic()
            with _lock:
                hit = _store.get(key)
                if hit and now - hit[0] < ttl:
                    return hit[1]
            value = fn(*args, **kwargs)
            with _lock:
                _store[key] = (now, value)
            return value

        return wrapper

    return decorator
