"""Executable member-facing social interaction aliases.

The canonical final-integration runtime already owns the social commands through
its legacy surface/runtime registry. This module is intentionally not registered
as a second command owner; it exists only as a compatibility surface for tools
that import the historical module directly.
"""
from __future__ import annotations

SOCIAL_ACTIONS = (
    "hug", "kiss", "pat", "kick", "slap", "punch", "highfive", "cuddle",
    "poke", "bonk", "bite", "wave", "wink", "dance", "roast", "cheer",
    "comfort", "tickle", "salute", "stare", "handshake", "fistbump",
    "shoulderpat", "cheers",
)


def register(app):
    """Compatibility no-op: canonical runtime registration remains authoritative."""
    return []
