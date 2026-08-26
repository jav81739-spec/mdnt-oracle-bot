"""Durable, concurrency-safe state primitives for restart-sensitive mini-games."""
from __future__ import annotations

from typing import Any

from core.storage import storage

MAX_STATE_BYTES = 48_000


class GameStateError(RuntimeError):
    """Raised when game state cannot be persisted safely."""


class GameState:
    def __init__(self, game: str, chat_id: int | str) -> None:
        self.game = str(game)
        self.chat_id = str(chat_id)
        self.key = f"game:{self.game}:{self.chat_id}"
        self.lock_key = f"game-lock:{self.game}:{self.chat_id}"

    async def load(self, default: dict[str, Any] | None = None) -> dict[str, Any]:
        value = await storage.load(self.key, default or {})
        return value if isinstance(value, dict) else dict(default or {})

    async def save(self, value: dict[str, Any], ttl: int | None = None) -> None:
        if not isinstance(value, dict):
            raise GameStateError("game state must be a mapping")
        # Protect Redis from accidentally persisting a giant transcript/object graph.
        if len(str(value).encode("utf-8")) > MAX_STATE_BYTES:
            raise GameStateError("game state exceeds safety limit")
        ok = await storage.save(self.key, value, ttl=ttl)
        if not ok:
            raise GameStateError("game state persistence failed")

    async def clear(self) -> None:
        await storage.delete(self.key)

    def lock(self, ttl: int = 30, wait: float = 2.0):
        return storage.lock(self.lock_key, ttl=ttl, wait=wait)
