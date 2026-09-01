"""Human-facing voice trigger detection for Midnight Oracle.

Explicit phrases activate voice mode. Matching is boundary-aware so ordinary
words such as ``bollywood`` do not accidentally trigger a voice note.
"""
from __future__ import annotations

import re

# Explicit requests are deterministic; ambient voice remains probabilistic.
VOICE_TRIGGERS = (
    "voice note", "voice", "voice mein", "voice me", "voice mein bolo",
    "voice me bolo", "voice mein bol", "voice me bol", "say it", "say that",
    "say something", "speak", "audio", "audio bhejo", "awaaz", "awaaz mein",
    "awaaz me", "awaaz mein bolo", "awaaz me bolo", "bol ke bata",
    "bolkar bata", "bol ke sunao", "bolkar sunao", "bolo", "sunao", "suno",
)

# Longest phrases first prevents a shorter phrase from masking a more precise
# request when callers inspect the matched trigger.
_SORTED_TRIGGERS = tuple(sorted(VOICE_TRIGGERS, key=len, reverse=True))


def wants_voice(text: str) -> bool:
    """Return true only for an explicit voice request, not substring matches."""
    low = " ".join(text.casefold().split())
    if not low:
        return False
    return any(re.search(rf"(?<!\\w){re.escape(trigger)}(?!\\w)", low) for trigger in _SORTED_TRIGGERS)
