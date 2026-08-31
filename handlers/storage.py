"""Compatibility storage API for legacy handlers.

All persistence now goes through ``core.storage``. Keeping this tiny facade
lets existing handlers migrate incrementally without maintaining a second
backend implementation.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from core.storage import storage

redis_client = storage


def is_configured() -> bool:
    return storage.configured


async def save(key: str, value: Any, ttl: int | None = None) -> bool:
    return await storage.set(key, value, ttl=ttl)


async def load(key: str, default: Any = None) -> Any:
    value = await storage.get(key, default)
    if isinstance(value, str):
        import json
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


@asynccontextmanager
async def lock(key: str):
    """Process-local compatibility lock used by legacy command handlers.

    Persistent values still use the canonical Storage backend; this only
    serializes concurrent handlers inside this bot process and never creates
    another persistence backend.
    """
    async with _locks_guard:
        mutex = _locks.setdefault(str(key), asyncio.Lock())
    acquired = False
    try:
        await mutex.acquire()
        acquired = True
        yield acquired
    finally:
        if acquired:
            mutex.release()
