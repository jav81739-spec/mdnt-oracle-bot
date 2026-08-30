"""Small in-process flood guard for conversational handlers."""
from __future__ import annotations
from collections import defaultdict
from time import monotonic

_last_reply: dict[str, float] = defaultdict(float)

def cooldown_seconds(chat_type: str, direct: bool) -> float:
    """Return the conversational cooldown for direct versus ambient traffic."""
    if direct:
        return 3.0
    return 45.0

def is_cooling(key: str, seconds: float) -> bool:
    """Atomically reserve the next reply slot for a key."""
    now = monotonic()
    last = _last_reply[key]
    if now - last < seconds:
        return True
    _last_reply[key] = now
    return False
