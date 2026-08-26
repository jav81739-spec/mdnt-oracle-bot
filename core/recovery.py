"""Restart recovery for durable Midnight jobs."""
from __future__ import annotations

import logging
from typing import Any

from .storage import Storage, storage

log = logging.getLogger("midnight.recovery")


def _sanitize_state(state: Any) -> tuple[dict[str, Any], int]:
    """Return safe v2 state and count resumable chat sessions."""
    if not isinstance(state, dict):
        return {"chats": {}}, 0
    chats = state.get("chats")
    if not isinstance(chats, dict):
        return {"chats": {}}, 0
    clean: dict[str, Any] = {}
    active = 0
    for chat_id, raw in chats.items():
        if not isinstance(raw, dict):
            continue
        mafia = raw.get("mafia")
        survival = raw.get("survival")
        if not isinstance(mafia, dict):
            mafia = {"status": "none", "host": None, "players": {}, "order": [], "night_target": None, "votes": {}}
        if mafia.get("status") not in {"none", "lobby", "night", "day"}:
            mafia["status"] = "none"
        if not isinstance(mafia.get("players"), dict):
            mafia["players"] = {}
        if not isinstance(mafia.get("order"), list):
            mafia["order"] = []
        if not isinstance(mafia.get("votes"), dict):
            mafia["votes"] = {}
        if not isinstance(survival, dict):
            survival = {}
        raw["mafia"], raw["survival"] = mafia, survival
        clean[str(chat_id)] = raw
        if mafia.get("status") in {"lobby", "night", "day"}:
            active += 1
    return {"chats": clean}, active


async def recover_deathgames(application, legacy_module, store: Storage = storage) -> int:
    """Validate v2 state after restart and preserve resumable games."""
    state = await store.load("deathgames:v2", None)
    if state is None:
        legacy = await store.load("deathgames", {})
        state = {"chats": legacy} if isinstance(legacy, dict) else {"chats": {}}
    clean, active = _sanitize_state(state)
    if clean != state:
        if not await store.save("deathgames:v2", clean):
            raise RuntimeError("could not persist repaired death-game state")
        log.warning("Repaired malformed persisted death-game state")
    legacy_keys = await store.scan("dg_active:*")
    if legacy_keys:
        log.info("Ignoring %d obsolete death-game timer key(s); v2 state is authoritative", len(legacy_keys))
    if active:
        log.info("Restart recovery preserved %d active death-game chat(s)", active)
    return active
