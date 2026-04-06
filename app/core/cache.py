"""Redis client + cache utilities with msgpack serialization.

Redis is fully optional. If REDIS_URL is not set or the server is
unreachable, all cache operations become silent no-ops and the app
continues normally without caching.
"""
from __future__ import annotations

import functools
import hashlib
from collections.abc import Callable
from typing import Any, TypeVar

import msgpack
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None
_redis_disabled: bool = False  # set to True permanently after first failed ping

F = TypeVar("F", bound=Callable[..., Any])


def _is_redis_configured() -> bool:
    """Return True only if a non-default Redis URL is configured."""
    settings = get_settings()
    url = settings.redis_url or ""
    # Treat the default localhost URL as "not configured" in production
    if settings.app_env == "production" and "localhost" in url:
        return False
    return bool(url)


def get_redis() -> aioredis.Redis | None:
    """Return Redis client, or None if Redis is not configured/available."""
    global _redis_client, _redis_disabled  # noqa: PLW0603
    if _redis_disabled:
        return None
    if not _is_redis_configured():
        return None
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=False,  # we use msgpack bytes
            max_connections=20,
            health_check_interval=30,
        )
        logger.info("redis_client_created", url=settings.redis_url)
    return _redis_client


async def check_redis_health() -> bool:
    global _redis_disabled  # noqa: PLW0603
    if not _is_redis_configured():
        logger.info("redis_not_configured", hint="Set REDIS_URL to enable caching.")
        return False
    try:
        client = get_redis()
        if client is None:
            return False
        result = await client.ping()
        return bool(result)
    except Exception as exc:
        logger.warning("redis_unreachable", error=str(exc), hint="Caching disabled.")
        _redis_disabled = True
        return False


def _make_cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    raw = f"{prefix}:{args}:{sorted(kwargs.items())}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"geotrade:{prefix}:{digest}"


async def cache_get(key: str) -> Any | None:
    client = get_redis()
    if client is None:
        return None
    try:
        data = await client.get(key)
        if data is None:
            return None
        return msgpack.unpackb(data, raw=False)
    except Exception:
        return None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    client = get_redis()
    if client is None:
        return
    settings = get_settings()
    ttl = ttl or settings.redis_cache_ttl_seconds
    try:
        packed = msgpack.packb(value, default=str, use_bin_type=True)
        await client.setex(key, ttl, packed)
    except Exception:
        # Silent — never log a warning per-request when Redis is down
        pass


async def cache_delete(key: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.delete(key)
    except Exception:
        pass


async def cache_delete_prefix(prefix: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        keys = await client.keys(f"geotrade:{prefix}:*")
        if keys:
            await client.delete(*keys)
    except Exception:
        pass


def cached(prefix: str, ttl: int | None = None) -> Callable[[F], F]:
    """Decorator for async functions returning JSON-serialisable data."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _make_cache_key(prefix, *args, **kwargs)
            hit = await cache_get(key)
            if hit is not None:
                logger.debug("cache_hit", key=key)
                return hit
            result = await func(*args, **kwargs)
            await cache_set(key, result, ttl=ttl)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
