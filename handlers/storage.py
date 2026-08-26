"""
Persistent storage using Upstash Redis's REST API.

This module is deliberately small and dependency-light. It exposes the
original save()/load() helpers plus a Redis-compatible async client used by
bot.py for counters, TTLs, lists, and atomic increments.

Render's filesystem is ephemeral, so persistent state belongs in Upstash.
When the environment variables are absent, operations fail closed and the
bot continues to run without persistence.
"""
import json
import os
from typing import Any

import httpx

UPSTASH_URL = (os.getenv("UPSTASH_REDIS_REST_URL") or "").rstrip("/")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN") or ""


def is_configured() -> bool:
    return bool(UPSTASH_URL and UPSTASH_TOKEN)


class UpstashRedis:
    """Small async Redis API adapter backed by Upstash REST commands."""

    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token

    async def _command(self, command: str, *args: Any):
        if not self.url or not self.token:
            return None

        # Upstash REST command routes are /<command>/<arg>... .
        encoded = [str(arg) for arg in args]
        path = "/".join([command, *encoded])
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.url}/{path}",
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                response.raise_for_status()
                payload = response.json()
                return payload.get("result")
        except (httpx.HTTPError, ValueError):
            return None

    async def get(self, key: str):
        return await self._command("get", key)

    async def set(self, key: str, value: Any):
        if isinstance(value, (dict, list, tuple)):
            value = json.dumps(value)
        return await self._command("set", key, value)

    async def setex(self, key: str, seconds: int, value: Any):
        if isinstance(value, (dict, list, tuple)):
            value = json.dumps(value)
        return await self._command("setex", key, int(seconds), value)

    async def delete(self, *keys: str):
        return await self._command("del", *keys)

    async def exists(self, key: str):
        return await self._command("exists", key)

    async def keys(self, pattern: str = "*"):
        result = await self._command("keys", pattern)
        return result or []

    async def ttl(self, key: str):
        result = await self._command("ttl", key)
        return int(result) if result is not None else -1

    async def expire(self, key: str, seconds: int):
        return await self._command("expire", key, int(seconds))

    async def lpush(self, key: str, *values: Any):
        return await self._command("lpush", key, *values)

    async def lrange(self, key: str, start: int, end: int):
        result = await self._command("lrange", key, int(start), int(end))
        return result or []

    async def incrby(self, key: str, amount: int = 1):
        """Atomically increment a numeric key and return the new value."""
        result = await self._command("incrby", key, int(amount))
        return int(result) if result is not None else None


# bot.py discovers this attribute before attempting any optional redis
# package import, so the production path uses the already-installed httpx.
redis_client = UpstashRedis(UPSTASH_URL, UPSTASH_TOKEN)


async def save(key: str, value) -> None:
    if not is_configured():
        return
    await redis_client.set(key, value)


async def load(key: str, default=None):
    if not is_configured():
        return default
    result = await redis_client.get(key)
    if result is None:
        return default
    try:
        return json.loads(result)
    except (TypeError, json.JSONDecodeError):
        return result
