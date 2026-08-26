"""Health/readiness helpers for Render and UptimeRobot."""
from __future__ import annotations

from dataclasses import dataclass

from .storage import Storage, storage


@dataclass
class Health:
    status: str
    storage: str
    bot: str = "unknown"

    def as_dict(self) -> dict[str, str]:
        return {"status": self.status, "bot": self.bot, "storage": self.storage}


async def check(store: Storage = storage) -> Health:
    if not store.configured:
        return Health("degraded", "unconfigured")
    try:
        await store.set("health:midnight", "ok", ttl=30)
        return Health("ok", "ok")
    except Exception:
        return Health("degraded", "error")
