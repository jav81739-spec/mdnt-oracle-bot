"""Persistence boundary for legacy multi-turn games."""
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


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"__set__"}:
            return {_decode(item) for item in value["__set__"]}
        result = {}
        for key, item in value.items():
            try:
                decoded_key = int(key)
            except (TypeError, ValueError):
                decoded_key = key
            result[decoded_key] = _decode(item)
        return result
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def _restore(name: str, value: Any) -> Any:
    decoded = _decode(value)
    if name == "active_hangman" and isinstance(decoded, dict):
        for game in decoded.values():
            if isinstance(game, dict) and isinstance(game.get("guessed"), list):
                game["guessed"] = set(game["guessed"])
    return decoded


def persistent_game_state(
    *names: str,
    state_key: str | None = None,
    ttl: int = 86400,
) -> Callable:
    """Persist selected handler state and serialize commands per chat/game."""
    if not names:
        raise ValueError("at least one state name is required")

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        key_name = state_key or func.__name__

        @wraps(func)
        async def wrapper(update, context):
            chat_id = getattr(getattr(update, "effective_chat", None), "id", None)
            if chat_id is None:
                return await func(update, context)
            state = GameState(f"handler-{key_name}", chat_id)
            async with state.lock():
                module_globals = func.__globals__
                previous = {name: module_globals[name] for name in names}
                try:
                    persisted = await state.load({})
                    for name in names:
                        module_globals[name] = _restore(name, persisted.get(name, {}))
                    result = await func(update, context)
                    await state.save(
                        {name: _encode(module_globals[name]) for name in names},
                        ttl=ttl,
                    )
                    return result
                finally:
                    for name, value in previous.items():
                        module_globals[name] = value

        return wrapper

    return decorator
