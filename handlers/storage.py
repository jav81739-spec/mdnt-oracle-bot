"""Compatibility storage API for legacy handlers.

All persistence now goes through ``core.storage``. Keeping this tiny facade
lets existing handlers migrate incrementally without maintaining a second
backend implementation.
"""
from __future__ import annotations

from typing import Any

from core.storage import storage


def is_configured() -> bool:
    return storage.configured


async def save(key: str, value: Any, ttl: int | None = None) -> bool:
    return await storage.set(key, value, ttl=ttl)


async def load(key: str, default: Any = None) -> Any:
    value = await storage.get(key, default)
    if isinstance(value, str):
        # The core storage returns strings for legacy scalar values. JSON values
        # are decoded here for old handlers that previously called json.loads().
        import json
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value
