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
        """Transitional compatibility for legacy commands.

        KEYS is intentionally not used by new code because it can become
        expensive on large Redis datasets. Existing legacy commands still need
        this surface, so they use the real Redis command rather than silently
        returning an empty list as the previous adapter did.
        """
        if not storage.configured:
            async with storage._local_lock:
                return [key for key in storage._local if _glob_match(key, pattern)]
        result = await storage._request("POST", "/", json=["KEYS", pattern])
        return list(result or [])

    async def lpush(self, key, *values):
        return await storage.lpush(key, *values)

    async def lrange(self, key, start, end):
        return await storage.lrange(key, start, end)


def _glob_match(value: str, pattern: str) -> bool:
    """Small glob matcher for the local compatibility fallback."""
    import fnmatch
    return fnmatch.fnmatchcase(value, pattern)


redis_client = RedisCompat()
