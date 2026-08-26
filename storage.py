"""Compatibility facade used by the legacy bot.py.

The old entrypoint dynamically imports a top-level ``storage`` module and
expects a Redis-like object. This adapter makes the new core storage layer the
single backend without requiring a second Redis client.
"""
from core.storage import storage


class RedisCompat:
    async def get(self, key):
        return await storage.get(key, None)

    async def set(self, key, value):
        return await storage.set(key, value)

    async def setex(self, key, ttl, value):
        return await storage.set(key, value, ttl=ttl)

    async def exists(self, key):
        return int(await storage.exists(key))

    async def delete(self, *keys):
        return await storage.delete(*keys)

    async def ttl(self, key):
        return await storage.ttl(key)

    async def expire(self, key, ttl):
        current = await storage.get(key, None)
        if current is None:
            return False
        return await storage.set(key, current, ttl=ttl)

    async def incrby(self, key, amount):
        return await storage.incrby(key, amount)

    async def keys(self, pattern="*"):
        # Deliberately do not expose an unbounded KEYS scan over Upstash REST.
        # Legacy callers must migrate to indexed repositories.
        return []

    async def lpush(self, key, *values):
        return 0

    async def lrange(self, key, start, end):
        return []


redis_client = RedisCompat()
