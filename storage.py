"""Compatibility facade for the canonical async storage engine."""
from core.storage import storage


class RedisCompat:
    async def get(self, key):
        return await storage.get(key, None)

    async def set(self, key, value, ttl=None):
        return await storage.set(key, value, ttl=ttl)

    async def setex(self, key, ttl, value):
        return await storage.set(key, value, ttl=ttl)

    async def setnx(self, key, value, ttl=15):
        return await storage.setnx(key, value, ttl=ttl)

    async def eval(self, script, keys=(), args=()):
        return await storage.eval(script, list(keys), list(args))

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

    async def incr(self, key):
        return await storage.incrby(key, 1)

    async def incrby(self, key, amount):
        return await storage.incrby(key, amount)

    async def keys(self, pattern="*"):
        return await storage.scan(pattern)

    async def lpush(self, key, *values):
        return await storage.lpush(key, *values)

    async def lrange(self, key, start, end):
        return await storage.lrange(key, start, end)


def _glob_match(value: str, pattern: str) -> bool:
    import fnmatch
    return fnmatch.fnmatchcase(value, pattern)


redis_client = RedisCompat()
