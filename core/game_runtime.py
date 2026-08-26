"""Persistence boundary for legacy multi-turn games.

The existing handlers keep their gameplay logic, but their mutable state is
loaded from and committed to durable storage around every command.  This
provides restart recovery and per-game serialization without changing the
public command surface.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Awaitable, Callable

from core.game_state import GameState


def _encode(value: Any) -> Any:
    if isinstance(value, set):
        return {"__set__": [_encode(item) for item in value]}
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    return value


def _decode(value: Any, *, set_fields: bool = False) -> Any:
    if isinstance(value, dict):
        if set_fields and set(value) == {"__set__"}:
            return {_decode(item, set_fields=False) for item in value["__set__"]}
        result = {}
        for key, item in value.items():
            try:
                decoded_key = int(key)
            except (TypeError, ValueError):
                decoded_key = key
            result[decoded_key] = _decode(item, set_fields=set_fields)
        return result
    if isinstance(value, list):
        return [_decode(item, set_fields=set_fields) for item in value]
    return value


def _restore(name: str, value: Any) -> Any:
    decoded = _decode(value, set_fields=True)
    if name == "active_hangman":
        for game in decoded.values() if isinstance(decoded, dict) else ():
            if isinstance(game, dict) and isinstance(game.get("guessed"), list):
                game["guessed"] = set(game["guessed"])
    return decoded


def _snapshot(value: Any) -> Any:
    return _encode(value)


def persistent_game_state(*names: str, ttl: int = 86400) -> Callable:
    """Wrap a handler so its selected module-level state is durable and locked."""
    if not names:
        raise ValueError("at least one state name is required")

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def wrapper(update, context):
            chat = getattr(update, "effective_chat", None)
            chat_id = getattr(chat, "id", None)
            if chat_id is None:
                return await func(update, context)

            state = GameState(f"handler-{func.__name__}", chat_id)
            async with state.lock():
                module_globals = func.__globals__
                previous = {name: module_globals[name] for name in names}
                try:
                    persisted = await state.load({})
                    for name in names:
                        module_globals[name] = _restore(name, persisted.get(name, {}))
                    result = await func(update, context)
                    payload = {name: _snapshot(module_globals[name]) for name in names}
                    await state.save(payload, ttl=ttl)
                    return result
                finally:
                    for name, value in previous.items():
                        module_globals[name] = value

        return wrapper

    return decorator
