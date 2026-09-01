"""Human-facing voice trigger detection for Midnight Oracle.

Only explicit requests for a voice note activate voice mode. Ordinary
sentences containing words such as ``voice`` or ``audio`` stay in normal
conversation so Midnight does not misfire.
"""
from __future__ import annotations

import re

# Deliberately phrase-based. Single words like ``voice``, ``audio``, ``bolo``
# and ``suno`` are too common in ordinary conversation to be safe triggers.
VOICE_TRIGGERS = (
    "voice note",
    "send me a voice",
    "send a voice",
    "send voice",
    "voice bhejo",
    "voice bhej",
    "voice do",
    "voice please",
    "voice pls",
    "voice mein bolo",
    "voice me bolo",
    "voice mein bol",
    "voice me bol",
    "voice mein batao",
    "voice me batao",
    "voice mein bata",
    "voice me bata",
    "say it",
    "say that",
    "say something",
    "say it in voice",
    "speak it",
    "speak in voice",
    "send audio",
    "send me audio",
    "audio bhejo",
    "audio bhej",
    "awaaz mein bolo",
    "awaaz me bolo",
    "awaaz mein bol",
    "awaaz me bol",
    "awaaz mein batao",
    "awaaz me batao",
    "bol ke bata",
    "bolkar bata",
    "bol ke sunao",
    "bolkar sunao",
    "suna do",
)

_SORTED_TRIGGERS = tuple(sorted(VOICE_TRIGGERS, key=len, reverse=True))


def wants_voice(text: str) -> bool:
    """Return true only for an explicit voice-note request."""
    low = " ".join((text or "").casefold().split())
    if not low:
        return False
    return any(
        re.search(rf"(?<!\w){re.escape(trigger)}(?!\w)", low)
        for trigger in _SORTED_TRIGGERS
    )
