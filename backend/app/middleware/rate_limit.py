"""
Rate limiting middleware — per-user request throttling via Redis.

Implements TRD §9.2 rate limiting:
  - Chat: 60 requests/minute per user
  - Fine-tune: 10 requests/minute per user
  - General: 120 requests/minute per user

Uses Redis sliding window counters for accurate rate limiting.
Falls back to in-memory counting if Redis is unavailable.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

import redis.asyncio as redis
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────


@dataclass
class RateLimitConfig:
    """Rate limit configuration per endpoint group."""

    max_requests: int
    window_seconds: int = 60


# Rate limits by path prefix
RATE_LIMITS: dict[str, RateLimitConfig] = {
    "/api/v1/chat": RateLimitConfig(max_requests=60, window_seconds=60),
    "/api/v1/fine-tune": RateLimitConfig(max_requests=10, window_seconds=60),
    "/api/v1/evaluations": RateLimitConfig(max_requests=20, window_seconds=60),
    "/api/v1/analytics": RateLimitConfig(max_requests=30, window_seconds=60),
    "/api/auth/callback/credentials": RateLimitConfig(max_requests=5, window_seconds=60),
}

# Default rate limit for unmatched paths
DEFAULT_RATE_LIMIT = RateLimitConfig(max_requests=120, window_seconds=60)


# ── In-Memory Fallback ────────────────────────────────────────────────


@dataclass
class _MemoryCounter:
    """In-memory sliding window counter (fallback when Redis is unavailable)."""

    windows: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def check(self, key: str, config: RateLimitConfig) -> bool:
        """Check if a request is within the rate limit."""
        now = time.time()
        window_start = now - config.window_seconds

        # Clean old entries
        self.windows[key] = [ts for ts in self.windows[key] if ts > window_start]

        if len(self.windows[key]) >= config.max_requests:
            return False

        self.windows[key].append(now)
        return True

    def remaining(self, key: str, config: RateLimitConfig) -> int:
        """Get remaining requests in current window."""
        now = time.time()
        window_start = now - config.window_seconds
        current = len([ts for ts in self.windows[key] if ts > window_start])
        return max(0, config.max_requests - current)


_memory_counter = _MemoryCounter()


# ── Redis Counter ─────────────────────────────────────────────────────


_redis_client: redis.Redis | None = None


async def _get_redis() -> redis.Redis | None:
    """Get or create the Redis client."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await _redis_client.ping()
        except Exception:
            logger.warning("Redis unavailable — falling back to in-memory rate limiting")
            _redis_client = None
    return _redis_client


async def _redis_check(key: str, config: RateLimitConfig) -> bool:
    """Check rate limit using Redis sliding window."""
    client = await _get_redis()
    if client is None:
        return _memory_counter.check(key, config)

    try:
        now = time.time()
        window_start = now - config.window_seconds
        pipe = client.pipeline()

        # Remove old entries and count current ones
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, config.window_seconds)

        results = await pipe.execute()
        current_count = results[1]

        if current_count >= config.max_requests:
            # Remove the entry we just added
            await client.zrem(key, str(now))
            return False

        return True

    except Exception:
        logger.warning("Redis rate limit check failed — falling back to memory")
        return _memory_counter.check(key, config)


async def _redis_remaining(key: str, config: RateLimitConfig) -> int:
    """Get remaining requests using Redis."""
    client = await _get_redis()
    if client is None:
        return _memory_counter.remaining(key, config)

    try:
        now = time.time()
        window_start = now - config.window_seconds
        await client.zremrangebyscore(key, 0, window_start)
        count = await client.zcard(key)
        return max(0, config.max_requests - count)
    except Exception:
        return _memory_counter.remaining(key, config)


# ── Rate Limit Check ──────────────────────────────────────────────────


def _get_rate_config(path: str) -> RateLimitConfig:
    """Get the rate limit config for a request path."""
    for prefix, config in RATE_LIMITS.items():
        if path.startswith(prefix):
            return config
    return DEFAULT_RATE_LIMIT


def _extract_user_id(request: Request) -> str | None:
    """Extract user ID from the request state (set by auth middleware)."""
    # The auth dependency sets user info on the request state
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "user_id"):
        return user.user_id
    # Fallback: use client IP
    client = request.client
    return client.host if client else "unknown"


async def check_rate_limit(request: Request) -> None:
    """
    Check if the request is within the rate limit.

    Raises HTTPException(429) if the limit is exceeded.
    """
    path = request.url.path
    config = _get_rate_config(path)
    user_id = _extract_user_id(request) or "anonymous"

    key = f"ratelimit:{user_id}:{path}"
    allowed = await _redis_check(key, config)

    if not allowed:
        remaining = await _redis_remaining(key, config)
        logger.warning(
            "Rate limit exceeded: user=%s path=%s limit=%d/%ds",
            user_id,
            path,
            config.max_requests,
            config.window_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "limit": config.max_requests,
                "window_seconds": config.window_seconds,
                "retry_after": config.window_seconds,
            },
            headers={
                "X-RateLimit-Limit": str(config.max_requests),
                "X-RateLimit-Remaining": str(remaining),
                "Retry-After": str(config.window_seconds),
            },
        )


# ── Middleware ─────────────────────────────────────────────────────────


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that enforces per-user rate limits.

    Only applies to API routes (paths starting with /api/).
    Health check and auth routes are excluded.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip rate limiting for non-API routes and health checks
        if not path.startswith("/api/") or path.startswith("/api/v1/health"):
            return await call_next(request)

        # Skip for OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        try:
            await check_rate_limit(request)
        except HTTPException as exc:
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
                headers=exc.headers,
            )

        response = await call_next(request)

        # Add rate limit headers to successful responses
        user_id = _extract_user_id(request) or "anonymous"
        config = _get_rate_config(path)
        key = f"ratelimit:{user_id}:{path}"
        remaining = await _redis_remaining(key, config)

        response.headers["X-RateLimit-Limit"] = str(config.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
