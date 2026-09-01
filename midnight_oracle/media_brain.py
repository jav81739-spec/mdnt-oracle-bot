"""Context-triggered media augmentation for Midnight Oracle.

Media is additive: existing text is preserved and, when the moment warrants it,
a single GIF/sticker/photo is attached. The brain is deliberately conservative
to avoid turning every interaction into a media flood.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any

from telegram import Update


@dataclass(frozen=True)
class MediaDecision:
    kind: str
    query: str
    probability: float


# Explicit interaction commands get a higher media chance; ordinary chat stays quiet.
_COMMANDS = {
    "kiss": ("gif", "cute kiss reaction", 0.72),
    "hug": ("gif", "warm hug reaction", 0.66),
    "cuddle": ("gif", "cozy cuddle reaction", 0.66),
    "slap": ("gif", "playful slap reaction", 0.64),
    "bonk": ("gif", "funny bonk reaction", 0.70),
    "pat": ("sticker", "cute head pat reaction", 0.62),
    "poke": ("sticker", "playful poke reaction", 0.58),
    "bite": ("gif", "playful bite reaction", 0.52),
    "tickle": ("gif", "funny tickle reaction", 0.62),
    "highfive": ("gif", "celebratory high five reaction", 0.60),
    "wave": ("sticker", "friendly wave reaction", 0.52),
    "ship": ("gif", "romantic awkward reaction", 0.50),
    "bond": ("gif", "friendship warm reaction", 0.46),
    "friendship": ("gif", "best friends reaction", 0.44),
    "randomship": ("gif", "surprised shipping reaction", 0.52),
    "matchmaker": ("gif", "matchmaking reaction", 0.48),
    "roast": ("gif", "funny roast reaction", 0.42),
    "compliment": ("sticker", "happy compliment reaction", 0.40),
    "dare": ("gif", "dramatic dare reaction", 0.42),
    "truth": ("sticker", "curious truth reaction", 0.35),
}

# Topic reactions are intentionally lower probability than interaction commands.
_TOPICS = (
    ("cricket", "cricket reaction", 0.28),
    ("football", "football reaction", 0.25),
    ("movie", "cinema reaction", 0.22),
    ("film", "cinema reaction", 0.22),
    ("match", "sports reaction", 0.20),
    ("goal", "football celebration", 0.28),
    ("wicket", "cricket wicket reaction", 0.28),
    ("six", "cricket six celebration", 0.25),
    ("win", "celebration reaction", 0.22),
    ("birthday", "birthday celebration", 0.30),
)


def _chance(seed: str) -> float:
    return int.from_bytes(hashlib.sha256(seed.encode()).digest()[:4], "big") / 2**32


def decide(update: Update, command: str | None = None, text: str = "") -> MediaDecision | None:
    """Return at most one media decision for this moment."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return None
    key = (command or "").casefold().lstrip("/")
    chosen = _COMMANDS.get(key)
    if chosen:
        kind, query, probability = chosen
    else:
        low = (text or "").casefold()
        matches = [(k, q, p) for k, q, p in _TOPICS if k in low]
        if not matches:
            return None
        idx = int.from_bytes(hashlib.sha256(f"{chat.id}:{user.id}:{low[:160]}".encode()).digest()[:2], "big") % len(matches)
        _, query, probability = matches[idx]
        kind = "gif"
    seed = f"{chat.id}:{user.id}:{key}:{text[-180:]}:{int(time.time() // 90)}"
    if _chance(seed) > probability:
        return None
    return MediaDecision(kind=kind, query=query, probability=probability)


def enabled() -> bool:
    return bool((os.getenv("GIPHY_API_KEY") or "").strip())
