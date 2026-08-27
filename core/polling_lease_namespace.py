"""Namespace the Telegram polling lease by bot identity.

A revoked Telegram bot token must not remain blocked by a stale lease owned by
an older process. The lease owner key is deliberately derived from a one-way
hash of BOT_TOKEN, never from the token itself. Processes using the same bot
still share one lease and therefore remain protected against duplicate
getUpdates pollers.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any

from .storage import Storage

_LEGACY_POLLING_LEASE_KEY = "midnight:telegram:polling-lease:v2"


def _namespaced_key(key: str) -> str:
    if key != _LEGACY_POLLING_LEASE_KEY:
        return key
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        return key
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
    return f"{key}:{digest}"

_original_setnx = Storage.setnx
_original_eval = Storage.eval


async def _setnx_namespaced(self: Storage, key: str, value: str, ttl: int = 15) -> bool:
    return await _original_setnx(self, _namespaced_key(key), value, ttl)


async def _eval_namespaced(self: Storage, script: str, keys: list[str] | tuple[str, ...] = (), args: list[str] | tuple[str, ...] = ()) -> Any:
    mapped = [_namespaced_key(key) for key in keys]
    return await _original_eval(self, script, mapped, args)


Storage.setnx = _setnx_namespaced
Storage.eval = _eval_namespaced

__all__ = ["_namespaced_key"]
