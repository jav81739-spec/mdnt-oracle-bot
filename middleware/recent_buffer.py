"""Durable recent-message buffer with a silent in-memory fallback."""
from __future__ import annotations
import json
from collections import deque

async def load_recent(storage_client, gid: str) -> deque[str]:
    if not storage_client:
        return deque(maxlen=8)
    try:
        raw = await storage_client.get(f"recent:{gid}")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "ignore")
        values = json.loads(raw) if raw else []
        return deque((str(v) for v in values)[-8:], maxlen=8)
    except Exception:
        return deque(maxlen=8)

async def save_recent(storage_client, gid: str, dq: deque) -> None:
    if not storage_client:
        return
    try:
        # RedisCompat exposes setex rather than the redis-py `ex=` keyword.
        await storage_client.setex(f"recent:{gid}", 86400, json.dumps(list(dq)[-8:]))
    except Exception:
        pass
