from functools import cache
from hashlib import sha256
from time import time

import redis.asyncio as aioredis


class RedisCache:
    __slots__ = ("client", "ttl", "available", "_fallback")

    def __init__(self, ttl: int = 43200):
        self.ttl = ttl
        self.client: aioredis.Redis | None = None
        self.available = False
        self._fallback: dict[str, tuple[str, float]] = {}

    async def connect(self, url: str) -> None:
        try:
            self.client = aioredis.from_url(url, decode_responses=True)
            await self.client.ping()
            self.available = True
            print(f"Redis connected: {url} (TTL: {self.ttl}s)")
        except Exception as e:
            print(f"Redis unavailable, using memory fallback: {e}")

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()

    async def get(self, key: str) -> str | None:
        if self.available:
            return await self.client.get(key)
        if (entry := self._fallback.get(key)) and time() < entry[1]:
            return entry[0]
        self._fallback.pop(key, None)
        return None

    async def set(self, key: str, value: str) -> None:
        if self.available:
            await self.client.setex(key, self.ttl, value)
        else:
            self._fallback[key] = (value, time() + self.ttl)

    async def clear(self) -> None:
        if self.available:
            await self.client.flushdb()
        else:
            self._fallback.clear()

    async def stats(self) -> dict:
        if self.available:
            info = await self.client.info("keyspace")
            return {"keys": info.get("db0", {}).get("keys", 0), "backend": "redis", "ttl_hours": self.ttl // 3600}
        return {"keys": len(self._fallback), "backend": "memory", "ttl_hours": self.ttl // 3600}

    @staticmethod
    @cache
    def make_key(query: str) -> str:
        return f"icda:q:{sha256(query.casefold().strip().encode()).hexdigest()[:16]}"
