"""Token-bucket rate limiter (stdlib only — no extra dependencies).

Uses a deque of timestamps per client key. Sweep stale buckets periodically
to prevent unbounded memory growth when many unique IPs are seen over time.
"""

from __future__ import annotations

import itertools
import threading
from collections import deque

from fastapi import HTTPException


class RateLimiter:
    """Per-key sliding-window rate limiter backed by timestamp deques.

    Args:
        requests: Maximum requests allowed within *window* seconds.
        window: Rolling time window in seconds.
        sweep_interval: How often (in requests) to evict fully-drained buckets.
    """

    def __init__(
        self,
        requests: int = 30,
        window: float = 60.0,
        sweep_interval: int = 500,
    ) -> None:
        self._max_requests = requests
        self._window = window
        self._sweep_interval = sweep_interval
        self._buckets: dict[str, deque] = {}
        self._lock = threading.Lock()
        # itertools.count() is thread-safe under the GIL; we still call it
        # inside _lock so the modulo check and bucket ops are one atomic block.
        self._counter = itertools.count(start=1)

    def check(self, key: str) -> None:
        """Raise HTTP 429 if *key* has exceeded the rate limit.

        Thread-safe. Periodically sweeps empty buckets to cap memory use.
        """
        import time

        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = deque()
            bucket = self._buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Rate limit exceeded: max {self._max_requests} requests "
                        f"per {int(self._window)}s"
                    ),
                )
            bucket.append(now)
            if next(self._counter) % self._sweep_interval == 0:
                stale = [k for k, b in self._buckets.items() if not b]
                for k in stale:
                    del self._buckets[k]

    def reset_key(self, key: str) -> None:
        """Remove a key's bucket (used in tests to avoid cross-test contamination)."""
        with self._lock:
            self._buckets.pop(key, None)
