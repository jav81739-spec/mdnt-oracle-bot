"""Concurrency hardening for the still-live legacy betting/vault economy.

This is intentionally a compatibility shim: it keeps the legacy key names and
user-facing command implementations intact while serializing mutations that
otherwise use read-modify-write Redis operations.
"""
from __future__ import annotations

import asyncio
import functools
import logging
from collections import defaultdict

log = logging.getLogger("midnight.legacy_economy_atomic")

_LOCAL_LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_CONFIGURED = False


def _key_lock(name: str):
    """Use canonical distributed storage when available, local lock otherwise."""
    try:
        from core.storage import storage
        return storage.lock(name, ttl=30)
    except Exception:
        return _LocalAsyncLock(_LOCAL_LOCKS[name])


class _LocalAsyncLock:
    def __init__(self, lock: asyncio.Lock):
        self._lock = lock

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()
        return False


def _with_lock(key_builder):
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapped(uid, *args, **kwargs):
            async with _key_lock(key_builder(uid)):
                return await fn(uid, *args, **kwargs)
        return wrapped
    return decorator


def harden(legacy_bot) -> None:
    """Patch only the legacy helpers/commands that have unsafe RMW paths."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    # _addcoins is a single-key read-modify-write. Wrap the original helper
    # rather than replacing _setcoins too: _addcoins calls _setcoins internally,
    # and nested acquisition of the same distributed lock would deadlock.
    original_add = getattr(legacy_bot, "_addcoins", None)
    if callable(original_add):
        @_with_lock(lambda uid: f"legacy:economy:coins:{uid}")
        async def atomic_add(uid, amount):
            return await original_add(uid, amount)
        legacy_bot._addcoins = atomic_add

    # Deposit/withdraw each move value between coins:<uid> and wallet:<uid>
    # with two writes. Serializing the entire command preserves its existing
    # vault-capacity rules while preventing two vault operations from crossing.
    for command_name in ("deposit_command", "withdraw_command"):
        original = getattr(legacy_bot, command_name, None)
        if not callable(original):
            continue

        @functools.wraps(original)
        async def wrapped_command(update, context, _original=original):
            user = getattr(update, "effective_user", None)
            uid = getattr(user, "id", None)
            if uid is None:
                return await _original(update, context)
            async with _key_lock(f"legacy:economy:vault:{uid}"):
                return await _original(update, context)

        setattr(legacy_bot, command_name, wrapped_command)

    _CONFIGURED = True
    log.info("Legacy economy atomic compatibility hardening enabled")
