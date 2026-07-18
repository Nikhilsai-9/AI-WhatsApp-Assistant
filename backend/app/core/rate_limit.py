"""
Redis-based rate limiting middleware.

Provides sliding window rate limiting for API endpoints.
"""

from __future__ import annotations

import hashlib
import time
from typing import Callable

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Redis-backed sliding window rate limiter.

    Usage:
        limiter = RateLimiter(redis_client, max_requests=5, window_seconds=60)
        await limiter.check("user:123:login")
    """

    def __init__(
        self,
        redis_client,
        max_requests: int = 5,
        window_seconds: int = 60,
    ) -> None:
        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def check(self, key: str) -> tuple[bool, int, int]:
        """
        Check if request is allowed. Returns (allowed, remaining, reset_in).
        """
        now = time.time()
        window_start = now - self.window_seconds
        redis_key = f"ratelimit:{key}"

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {str(now): now})
        pipe.expire(redis_key, self.window_seconds)
        results = await pipe.execute()

        current_count = results[1]
        remaining = max(0, self.max_requests - current_count - 1)
        reset_in = self.window_seconds

        if current_count >= self.max_requests:
            return False, 0, reset_in

        return True, remaining, reset_in

    async def close(self) -> None:
        """Close Redis connection."""
        await self.redis.close()


# Global rate limiter instances
_rate_limiters: dict[str, RateLimiter] = {}


def get_rate_limiter(name: str, max_requests: int = 5, window_seconds: int = 60) -> RateLimiter:
    """Get or create a rate limiter instance."""
    if name not in _rate_limiters:
        import redis.asyncio as redis
        from app.core.config import settings

        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        _rate_limiters[name] = RateLimiter(
            redis_client,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )
    return _rate_limiters[name]


async def check_rate_limit(
    key: str,
    max_requests: int = 5,
    window_seconds: int = 60,
) -> None:
    """
    Check rate limit and raise HTTPException if exceeded.
    Use this in route handlers.
    """
    limiter = get_rate_limiter(key, max_requests, window_seconds)
    allowed, remaining, reset_in = await limiter.check(key)

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
    """
    FastAPI dependency for rate limiting.

    Usage:
        @router.post("/login")
        async def login(
            form_data: OAuth2PasswordRequestForm = Depends(
                rate_limit_dependency(max_requests=5, window_seconds=60)
            )
        ):
            ...
    """
    import asyncio
    from functools import partial

    async def _check(request: Request) -> None:
        # Build rate limit key
        if key_func:
            key = key_func(request)
        else:
            # Default: IP-based
            client_ip = request.client.host if request.client else "unknown"
            path = request.url.path.replace("/", "_")
            key = f"{client_ip}:{path}"

        # Hash key to prevent injection
        safe_key = hashlib.sha256(key.encode()).hexdigest()[:16]
        await check_rate_limit(safe_key, max_requests, window_seconds)

    return _check