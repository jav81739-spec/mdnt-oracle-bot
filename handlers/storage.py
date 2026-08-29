"""Compatibility storage API for legacy handlers.

All persistence now goes through ``core.storage``. Keeping this tiny facade
lets existing handlers migrate incrementally without maintaining a second
backend implementation.
"""
from __future__ import annotations

from typing import Any

from core.storage import storage

# Legacy handlers expect a redis-like object named ``redis_client``.  The
# durable Storage facade intentionally exposes the same async primitives used
# by those handlers, so this alias preserves the old import without restoring
# a second persistence backend.
redis_client = storage


def is_configured() -> bool:
    """Return whether persistent storage is configured."""
    return storage.configured


async def save(key: str, value: Any, ttl: int | None = None) -> bool:
    """Persist a value through the canonical storage facade."""
    return await storage.set(key, value, ttl=ttl)


async def load(key: str, default: Any = None) -> Any:
    """Load a value and decode legacy JSON strings when possible."""
    value = await storage.get(key, default)
    if isinstance(value, str):
        import json
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value
