"""Human-facing voice trigger detection for Midnight Oracle."""
from __future__ import annotations

# Explicit requests are deterministic; ambient voice remains probabilistic.
VOICE_TRIGGERS = (
    "voice note", "voice", "voice mein", "voice me", "voice mein bolo",
    "voice me bolo", "say it", "say that", "say something", "speak",
    "audio", "audio bhejo", "awaaz", "awaaz mein", "awaaz me",
    "bol ke bata", "bolkar bata", "bolo", "bol", "sunao", "suno",
)


def wants_voice(text: str) -> bool:
    low = " ".join(text.casefold().split())
    if not low:
        return False
    return any(trigger in low for trigger in VOICE_TRIGGERS)
