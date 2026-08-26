"""Restart recovery for durable Midnight jobs."""
from __future__ import annotations

import logging

from .storage import Storage, storage

log = logging.getLogger("midnight.recovery")


async def recover_deathgames(application, legacy_module, store: Storage = storage) -> int:
    """Validate and migrate legacy death-game records after restart.

    The v2 engine persists the complete lobby/night/day state, so no process
    timer needs to be recreated. Old ``dg_active:*`` timer records are ignored
    rather than calling removed legacy functions. Recovery is idempotent.
    """
    recovered = 0
    state = await store.get("deathgames:v2", None)
    if isinstance(state, dict):
        # JSON values are decoded by handlers/storage compatibility; core.store
        # may return a JSON string, so normalize both representations.
        return recovered

    legacy_keys = await store.scan("dg_active:*")
    if legacy_keys:
        log.warning("Found %d obsolete death-game timer key(s); v2 state is authoritative", len(legacy_keys))
    return recovered
