"""Compatibility facade used by the legacy runtime.

The staged rebuild keeps the old Redis-like surface temporarily, but every
operation is backed by the single core storage engine. New code should import
``core.storage.storage`` directly.
"""
from core.storage import storage


class RedisCompat:
    async def get(self, key):
        return await storage.get(key, None)

    async def set(self, key, value):
        return await storage.set(key, value)

    async def setex(self, key, ttl, value):
        return await storage.set(key, value, ttl=ttl)

    async def setnx(self, key, value, ttl=15):
        return await storage.setnx(key, value, ttl=ttl)

    async def compare_set(self, key, expected, value, ttl=0):
        return await storage.compare_set(key, expected, value, ttl=ttl)

    async def eval(self, script, keys=(), args=()):
        """Expose the canonical atomic script primitive to startup/legacy code."""
        return await storage.eval(script, list(keys), list(args))

    async def exists(self, key):
        return int(await storage.exists(key))

    async def delete(self, *keys):
        return await storage.delete(*keys)

    async def ttl(self, key):
        return await storage.ttl(key)

    async def expire(self, key, ttl):
        current=await storage.get(key, None)
        if current is None:
            return False
        return await storage.set(key, current, ttl=ttl)

    async def incrby(self, key, amount):
        return await storage.incrby(key, amount)

    async def keys(self, pattern="*"):
        """Compatibility name backed by SCAN, never Redis KEYS."""
        return await storage.scan(pattern)

    async def lpush(self, key, *values):
        return await storage.lpush(key, *values)

    async def lrange(self, key, start, end):
        return await storage.lrange(key, start, end)


def _glob_match(value: str, pattern: str) -> bool:
    """Small glob matcher retained for callers importing this helper."""
    import fnmatch
    return fnmatch.fnmatchcase(value, pattern)


redis_client = RedisCompat()
