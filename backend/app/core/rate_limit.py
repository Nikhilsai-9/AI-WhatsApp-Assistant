"""
Redis-based rate limiting with in-memory fallback.

If Redis is unavailable, the limiter degrades to a per-process in-memory
sliding window — sufficient to prevent abuse during local development
and to avoid breaking the app when the Redis container is down.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import deque
from typing import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ─── In-memory fallback store ────────────────────────────────────
class InMemorySlidingWindow:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._buckets: dict[str, deque[float]] = {}

    async def check(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
        async with self._lock:
            now = time.time()
            cutoff = now - window_seconds
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= max_requests:
                remaining = 0
                reset_in = max(1, int(window_seconds - (now - bucket[0])))
                return False, remaining, reset_in
            bucket.append(now)
            remaining = max(0, max_requests - len(bucket))
            return True, remaining, window_seconds


_memory_limiter = InMemorySlidingWindow()
_redis_limiter = None  # lazy


async def _get_redis_limiter():
    global _redis_limiter
    if _redis_limiter is not None:
        return _redis_limiter
    try:
        import redis.asyncio as redis_async

        client = redis_async.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        # ping with timeout
        await asyncio.wait_for(client.ping(), timeout=2.0)
        _redis_limiter = client
        return client
    except Exception as exc:  # pragma: no cover — network optional
        logger.warning(f"Redis unavailable for rate limiting, using in-memory: {exc}")
        _redis_limiter = None
        return None


# ─── Public API ──────────────────────────────────────────────────
async def check_rate_limit(
    key: str,
    max_requests: int = 5,
    window_seconds: int = 60,
) -> None:
    """
    Check rate limit and raise HTTPException(429) if exceeded.
    Falls back to in-memory sliding window when Redis is unavailable.
    """
    full_key = f"ratelimit:{key}"
    client = await _get_redis_limiter()
    if client is not None:
        try:
            now = time.time()
            window_start = now - window_seconds
            pipe = client.pipeline()
            pipe.zremrangebyscore(full_key, 0, window_start)
            pipe.zcard(full_key)
            pipe.zadd(full_key, {str(now): now})
            pipe.expire(full_key, window_seconds)
            results = await asyncio.wait_for(pipe.execute(), timeout=2.0)
            current_count = results[1]
            if current_count >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {window_seconds} seconds.",
                    headers={
                        "Retry-After": str(window_seconds),
                        "X-RateLimit-Remaining": "0",
                    },
                )
            return
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Redis rate-limit failed, falling back to memory: {exc}")

    allowed, _remaining, reset_in = await _memory_limiter.check(full_key, max_requests, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {reset_in} seconds.",
            headers={"Retry-After": str(reset_in), "X-RateLimit-Remaining": "0"},
        )


def rate_limit_dependency(
    max_requests: int = 5,
    window_seconds: int = 60,
    key_func: Callable[[Request], str] | None = None,
):
    """FastAPI dependency factory."""
    async def _check(request: Request) -> None:
        if key_func:
            key = key_func(request)
        else:
            client_ip = request.client.host if request.client else "unknown"
            path = request.url.path.replace("/", "_")
            key = f"{client_ip}:{path}"
        safe_key = hashlib.sha256(key.encode()).hexdigest()[:16]
        await check_rate_limit(safe_key, max_requests, window_seconds)

    return _check