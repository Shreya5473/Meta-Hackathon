"""Redis client wrapper for market data caching.
Follows the requested structure while utilizing the existing core cache.
"""
from typing import Any, Optional
from app.core.cache import cache_get, cache_set, get_redis

class RedisClient:
    """Centralized Redis client for market data caching."""
    
    @staticmethod
    async def get(key: str) -> Optional[Any]:
        """Retrieve a value from the cache."""
        return await cache_get(key)

    @staticmethod
    async def set(key: str, value: Any, ttl: int = 10) -> None:
        """Store a value in the cache with a specific TTL (default 10s)."""
        await cache_set(key, value, ttl=ttl)

    @staticmethod
    async def is_available() -> bool:
        """Check if Redis is connected and available."""
        client = get_redis()
        return client is not None
