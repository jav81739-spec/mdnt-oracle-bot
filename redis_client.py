"""
redis_client.py — Universal Redis adapter for Midnight Oracle Bot

This file sits in the ROOT of your repo (same level as bot.py).
It wraps your existing storage.py so all new modules work without
touching your original code.

HOW IT WORKS:
Your storage.py likely exports one of these patterns:
  - redis_client  (direct aioredis/redis client object)
  - r             (common short name)
  - client        (another common name)
  - get_redis()   (function that returns a client)

This wrapper tries all known patterns and falls back gracefully.
If none match, update the STORAGE_EXPORT_NAME below to match
whatever name your storage.py actually exports.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import os
import importlib
import asyncio
from typing import Optional

# ─── Try to import from your existing storage.py ──────────────────────────
# We try multiple possible export names automatically

_redis = None

def _load_redis():
    global _redis
    if _redis is not None:
        return _redis

    # Try importing your storage module
    try:
        storage_mod = importlib.import_module("storage")
    except ModuleNotFoundError:
        try:
            storage_mod = importlib.import_module("handlers.storage")
        except ModuleNotFoundError:
            storage_mod = None

    if storage_mod:
        # Try common export names
        for attr in ["redis_client", "r", "client", "redis", "db", "aioredis_client", "rd"]:
            obj = getattr(storage_mod, attr, None)
            if obj is not None:
                _redis = obj
                return _redis

        # Try a factory function
        for func_name in ["get_redis", "get_client", "create_client", "get_db"]:
            func = getattr(storage_mod, func_name, None)
            if func is not None:
                try:
                    _redis = func()
                    return _redis
                except Exception:
                    pass

    # ── Fallback: create our own Redis client from env vars ────────────────
    # This runs if storage.py can't be found or doesn't export a client
    # Reads UPSTASH_REDIS_REST_URL / REDIS_URL from your Render env vars
    _redis = _create_fallback_client()
    return _redis


def _create_fallback_client():
    """
    Creates a direct Redis async client from environment variables.
    Works with Upstash Redis (your current setup).
    """
    import redis.asyncio as aioredis

    # Upstash provides these env vars
    redis_url = (
        os.getenv("UPSTASH_REDIS_REST_URL") or
        os.getenv("REDIS_URL") or
        os.getenv("KV_URL") or
        os.getenv("REDIS_URI")
    )
    redis_password = (
        os.getenv("UPSTASH_REDIS_REST_TOKEN") or
        os.getenv("REDIS_PASSWORD") or
        os.getenv("KV_REST_API_TOKEN")
    )

    if redis_url:
        # Convert Upstash HTTPS URL to redis:// if needed
        if redis_url.startswith("https://"):
            # Upstash REST URL — extract host
            host = redis_url.replace("https://", "").rstrip("/")
            client = aioredis.Redis(
                host=host,
                port=6379,
                password=redis_password,
                ssl=True,
                decode_responses=True,
            )
            return client
        elif redis_url.startswith("rediss://") or redis_url.startswith("redis://"):
            client = aioredis.from_url(redis_url, decode_responses=True)
            return client

    # Last resort: localhost (for local testing)
    return aioredis.Redis(host="localhost", port=6379, decode_responses=True)


# ─── Proxy class that mimics standard redis.asyncio interface ──────────────
class RedisClientProxy:
    """
    Wraps whatever your storage.py returns and provides a consistent
    async interface for all new Oracle modules.

    Supports both:
      - redis.asyncio style (native async methods)
      - Upstash REST HTTP style (some bots use this)
    """

    def __init__(self):
        self._client = None

    def _get(self):
        if self._client is None:
            self._client = _load_redis()
        return self._client

    async def get(self, key: str) -> Optional[str]:
        try:
            result = self._get().get(key)
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            print(f"[Redis] GET error for {key}: {e}")
            return None

    async def set(self, key: str, value: str) -> bool:
        try:
            result = self._get().set(key, value)
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            print(f"[Redis] SET error for {key}: {e}")
            return False

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        try:
            result = self._get().setex(key, ttl, value)
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            print(f"[Redis] SETEX error for {key}: {e}")
            return False

    async def delete(self, *keys) -> int:
        try:
            result = self._get().delete(*keys)
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            print(f"[Redis] DELETE error: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        try:
            result = self._get().exists(key)
            if asyncio.iscoroutine(result):
                return await result
            return bool(result)
        except Exception as e:
            print(f"[Redis] EXISTS error for {key}: {e}")
            return False

    async def keys(self, pattern: str = "*") -> list:
        try:
            result = self._get().keys(pattern)
            if asyncio.iscoroutine(result):
                return await result
            return result or []
        except Exception as e:
            print(f"[Redis] KEYS error for {pattern}: {e}")
            return []

    async def ttl(self, key: str) -> int:
        try:
            result = self._get().ttl(key)
            if asyncio.iscoroutine(result):
                return await result
            return result or -1
        except Exception as e:
            print(f"[Redis] TTL error for {key}: {e}")
            return -1

    async def lpush(self, key: str, *values) -> int:
        try:
            result = self._get().lpush(key, *values)
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            print(f"[Redis] LPUSH error for {key}: {e}")
            return 0

    async def lrange(self, key: str, start: int, end: int) -> list:
        try:
            result = self._get().lrange(key, start, end)
            if asyncio.iscoroutine(result):
                return await result
            return result or []
        except Exception as e:
            print(f"[Redis] LRANGE error for {key}: {e}")
            return []

    async def expire(self, key: str, ttl: int) -> bool:
        try:
            result = self._get().expire(key, ttl)
            if asyncio.iscoroutine(result):
                return await result
            return bool(result)
        except Exception as e:
            print(f"[Redis] EXPIRE error for {key}: {e}")
            return False

    async def incr(self, key: str) -> int:
        try:
            result = self._get().incr(key)
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            print(f"[Redis] INCR error for {key}: {e}")
            return 0


# ─── The singleton all modules import ─────────────────────────────────────
redis_client = RedisClientProxy()
