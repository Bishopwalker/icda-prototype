"""Caching with Redis or in-memory fallback.

Works in LITE MODE (no Redis) with automatic in-memory fallback.
"""

from functools import cache
from hashlib import sha256
from time import time


class RedisCache:
    """Async cache with Redis or in-memory fallback."""
    
    __slots__ = ("client", "ttl", "available", "_fallback")

    def __init__(self, ttl: int = 43200):
        self.ttl = ttl
        self.client = None
        self.available = False
        self._fallback: dict[str, tuple[str, float]] = {}

    async def connect(self, url: str) -> None:
        """Connect to Redis or use in-memory fallback."""
        if not url:
            print("Cache: Using in-memory (no Redis configured)")
            return
            
        try:
            import redis.asyncio as aioredis
            self.client = aioredis.from_url(url, decode_responses=True)
            await self.client.ping()
            self.available = True
            print(f"Cache: Redis connected ({url})")
        except ImportError:
            print("Cache: redis package not installed, using in-memory")
        except Exception as e:
            print(f"Cache: Redis unavailable ({e}), using in-memory")

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()

    async def get(self, key: str) -> str | None:
        if self.available:
            try:
                return await self.client.get(key)
            except Exception:
                pass
        # In-memory fallback
        if (entry := self._fallback.get(key)) and time() < entry[1]:
            return entry[0]
        self._fallback.pop(key, None)
        return None

    async def set(self, key: str, value: str) -> None:
        if self.available:
            try:
                await self.client.setex(key, self.ttl, value)
                return
            except Exception:
                pass
        # In-memory fallback
        self._fallback[key] = (value, time() + self.ttl)

    async def clear(self) -> None:
        if self.available:
            try:
                await self.client.flushdb()
                return
            except Exception:
                pass
        self._fallback.clear()

    async def stats(self) -> dict:
        if self.available:
            try:
                info = await self.client.info("keyspace")
                return {
                    "keys": info.get("db0", {}).get("keys", 0),
                    "backend": "redis",
                    "ttl_hours": self.ttl // 3600
                }
            except Exception:
                self.available = False
        return {
            "keys": len(self._fallback),
            "backend": "memory",
            "ttl_hours": self.ttl // 3600
        }

    @staticmethod
    @cache
    def make_key(query: str) -> str:
        return f"icda:q:{sha256(query.casefold().strip().encode()).hexdigest()[:16]}"
