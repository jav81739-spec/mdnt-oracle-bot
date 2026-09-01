"""Intent-safe voice trigger detection for Midnight Oracle."""
from __future__ import annotations

import re

# Deliberately phrase-based. Generic words such as "voice", "audio", "bolo",
# "suno", or "speak" are never sufficient on their own.
VOICE_TRIGGERS = (
    "send a voice note",
    "send me a voice note",
    "send a voice",
    "send me a voice",
    "voice note bhejo",
    "voice note bhej",
    "voice mein bolo",
    "voice me bolo",
    "voice mein bol",
    "voice me bol",
    "voice mein batao",
    "voice me batao",
    "voice mein bata",
    "voice me bata",
    "awaaz mein bolo",
    "awaaz me bolo",
    "awaaz mein bol",
    "awaaz me bol",
    "bol ke batao",
    "bol ke bata",
    "bolkar batao",
    "bolkar bata",
    "bol ke sunao",
    "bolkar sunao",
    "suna do",
    "say it in voice",
    "say that in voice",
    "say this in voice",
    "say it as a voice note",
    "send an audio note",
    "audio note bhejo",
)

_SORTED_TRIGGERS = tuple(sorted(VOICE_TRIGGERS, key=len, reverse=True))


def wants_voice(text: str) -> bool:
    """Return true only for a deliberate request to receive a voice note."""
    low = " ".join((text or "").casefold().split())
    if not low:
        return False
    return any(
        re.search(rf"(?<!\w){re.escape(trigger)}(?!\w)", low)
        for trigger in _SORTED_TRIGGERS
    )
