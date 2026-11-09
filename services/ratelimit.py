"""In-memory limit for AI routes. Enough for a laptop demo, not a public deployment."""

from __future__ import annotations

import time
from collections import defaultdict, deque

_buckets: dict[str, deque] = defaultdict(deque)


def allow(key: str, *, limit: int = 30, window: int = 600) -> bool:
    now = time.monotonic()
    bucket = _buckets[key]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def reset() -> None:
    _buckets.clear()
