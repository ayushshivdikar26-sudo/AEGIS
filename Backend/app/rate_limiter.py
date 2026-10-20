import contextlib
"""
AEGIS Redis-Backed Rate Limiter with Fail-Closed Protection (Backend/app/rate_limiter.py)
Enforces distributed request rate limits and fails closed on critical security routes if Redis fails (PRD Part 2c s7).
"""

from typing import cast

import redis
from fastapi import Request
from slowapi import Limiter

from Backend.app.config import settings
from Backend.app.deps import get_rate_limit_key
from Backend.app.errors import AppError, RateLimitExceededError
from Backend.app.logging_setup import logger

# Initialize Redis client for heartbeat & fail-closed verification
_redis_client: redis.Redis | None = None
_IN_MEMORY_RATE_LIMITS: dict[str, list[float]] = {}


def reset_rate_limits() -> None:
    """Clears in-memory and Redis rate limits for test isolation."""
    _IN_MEMORY_RATE_LIMITS.clear()
    with contextlib.suppress(Exception):
        limiter.reset()
    with contextlib.suppress(Exception):
        client = get_redis_client()
        if client and is_redis_available():
            keys = client.keys("rl:*")
            if keys:
                client.delete(*keys)


def get_redis_client() -> redis.Redis | None:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis.from_url(
                settings.RATE_LIMIT_STORAGE_URI,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
        except Exception as exc:
            logger.warning(f"Could not connect to Redis at {settings.RATE_LIMIT_STORAGE_URI}: {exc}")
            _redis_client = None
    return _redis_client


def is_redis_available() -> bool:
    client = get_redis_client()
    if not client:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False


# In local dev/testing without active Redis, slowapi can fall back to memory
try:
    if is_redis_available():
        limiter = Limiter(
            key_func=get_rate_limit_key,
            storage_uri=settings.RATE_LIMIT_STORAGE_URI,
        )
    else:
        limiter = Limiter(
            key_func=get_rate_limit_key,
            storage_uri="memory://",
        )
except Exception:
    limiter = Limiter(key_func=get_rate_limit_key, storage_uri="memory://")


def enforce_critical_route_rate_limit(
    request: Request, route_name: str, max_requests: int, window_seconds: int
) -> None:
    """
    Enforces rate limits on critical routes (login, signup, import).
    FAIL-CLOSED: If Redis is configured but unavailable in production, denies request with 503.
    """
    # If production, check Redis connectivity and fail closed
    if settings.ENVIRONMENT == "production" and not is_redis_available():
        logger.error(f"FAIL-CLOSED: Redis rate limiter unavailable for critical route {route_name}. Denying request.")
        raise AppError(
            "Security service unavailable. Please retry shortly.",
            code="rate_limiter_unavailable",
            status_code=503,
        )

    client = get_redis_client()
    key = f"rl:{route_name}:{get_rate_limit_key(request)}"

    if client and is_redis_available():
        try:
            current = cast(int, client.incr(key))
            if current == 1:
                client.expire(key, window_seconds)
            if current > max_requests:
                ttl = cast(int, client.ttl(key))
                raise RateLimitExceededError(
                    f"Too many requests for {route_name}. Try again in {ttl} seconds.",
                    retry_after=max(1, ttl),
                )
        except redis.RedisError as exc:
            if settings.ENVIRONMENT == "production":
                logger.error(f"FAIL-CLOSED: Redis error during rate limit check: {exc}")
                raise AppError(
                    "Security service unavailable.",
                    code="rate_limiter_unavailable",
                    status_code=503,
                )
    else:
        # Sliding window in-memory fallback for local testing
        import time

        now = time.time()
        timestamps = _IN_MEMORY_RATE_LIMITS.setdefault(key, [])
        timestamps[:] = [t for t in timestamps if now - t < window_seconds]
        if len(timestamps) >= max_requests:
            retry_after = int(window_seconds - (now - timestamps[0])) + 1
            raise RateLimitExceededError(
                f"Too many requests for {route_name}. Try again in {retry_after} seconds.",
                retry_after=max(1, retry_after),
            )
        timestamps.append(now)
