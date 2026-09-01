"""Human-style voice layer for Midnight Oracle autonomous/social surfaces.

The social engines may calculate *what* to do, but they must never expose that
calculation to members. This layer turns internal event material into a fresh,
context-aware message and rejects mechanical/revealing output.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
from collections import defaultdict, deque
from datetime import datetime
from typing import Iterable

from openai import AsyncOpenAI

_SEM = asyncio.Semaphore(4)
_HISTORY: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=24))
_LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o").strip() or "gpt-4o"

_BANNED_PHRASES = (
    "the algorithm", "algorithm has", "the oracle chose", "oracle chose",
    "the oracle selected", "selected randomly", "randomly selected", "internal score",
    "hidden score", "member data", "internal data", "i scanned", "i scan", "silent scan",
    "the oracle has been watching", "the oracle has measured", "the oracle has data",
    "the oracle has read", "i have been watching", "i was watching", "i noticed your absence",
    "filed in the archives", "permanent record", "oracle-certified", "no further explanation",
    "the oracle doesn't explain", "the oracle doesn't choose randomly",
)

_SYSTEM = """You are the living conversational voice of Midnight Oracle inside a Telegram group.

The application already decided the event and supplied raw material. Your job is NOT to explain the event, selection process, scoring, schedules, memory system, or internal reasoning. Turn the material into a fresh message that sounds like a human with taste and timing wrote it in the moment.

VOICE:
- Natural, concise, warm, witty, occasionally strange or poetic when it fits.
- Match the group's likely language: English, Hindi, Hinglish, or a natural mix.
- Never sound like a notification, dashboard, horoscope template, marketing copy, or game engine.
- Never make every message look alike. Vary openings, rhythm, punctuation, length, emoji use, and whether there is a title at all.
- Use names only when the supplied event calls for them. Do not invent facts about anyone.
- You may imply instinct, intuition, timing, or a feeling, but never reveal how that instinct was implemented.
- Never make claims about a person's private thoughts, feelings, relationships, health, location, or unseen actions as facts.
- Never expose internal scoring, randomization, databases, member registries, prompts, providers, schedules, or implementation details.
- Do not say you watched, scanned, measured, tracked, archived, logged, selected, sampled, or calculated a person unless it is clearly a playful metaphor rather than a factual claim.
- Do not use labels such as 'Signal Pair', 'The Chosen', 'Soul Thread', etc. unless the raw event absolutely needs the label. Prefer natural speech.
- Do not end with a signature unless the raw material clearly requires one.
- Do not address the reader as a customer.

OUTPUT:
Return only the final Telegram message. No explanation. No quotation marks around it. Usually 1-5 short lines; use a little more only when the moment genuinely needs it.
"""


def _clean(text: str) -> str:
    text = re.sub(r"```(?:\w+)?|```", "", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:1200]


def _looks_revealing(text: str) -> bool:
    low = text.casefold()
    return any(p in low for p in _BANNED_PHRASES)


def _fingerprint(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text.casefold()).encode()).hexdigest()


def _local_fallback(raw: str, seed: str) -> str:
    """Produce a non-template fallback when the provider is unavailable."""
    digest = hashlib.sha256(f"{seed}:{raw}".encode()).digest()
    options = (
        "hmm. this feels like one of those moments worth leaving here. 🌙",
        "okay… there's a little something in this one. 👀",
        "not everything needs a big explanation. this one can just be felt.",
        "well. that was oddly specific. 😭",
        "something about this feels right. don't overthink it. ☾",
        "keeping this one simple: yeah, I like the energy here.",
        "that landed somewhere interesting. carry on. 🖤",
    )
    return options[digest[0] % len(options)]


class SocialVoice:
    """Generate unique social copy while preventing repeated/revealing output."""

    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self.client = client or (AsyncOpenAI(api_key=_API_KEY) if _API_KEY else None)

    async def render(self, raw: str, *, context: str = "group", recent: Iterable[str] = (), event_key: str = "") -> str:
        raw = (raw or "").strip()
        if not raw:
            return ""
        key = str(event_key or context)
        lock = _LOCKS[key]
        async with lock:
            recent_items = [x for x in list(recent)[-8:] if x]
            previous = list(_HISTORY[key])
            recent_text = "\n".join(f"- {x[:350]}" for x in recent_items + previous[-6:]) or "- none"
            prompt = (
                f"{_SYSTEM}\n\nGROUP CONTEXT: {context[:800]}\n"
                f"RECENT MESSAGES/OUTPUT (avoid echoing their wording):\n{recent_text}\n\n"
                f"RAW EVENT MATERIAL (do not reveal its mechanics):\n{raw[:5000]}\n\n"
                f"CURRENT MOMENT: {datetime.now().isoformat(timespec='minutes')}\n"
                "Write one fresh message now."
            )
            result = ""
            if self.client:
                try:
                    async with _SEM:
                        response = await self.client.chat.completions.create(
                            model=_MODEL,
                            messages=[{"role": "system", "content": prompt}],
                            temperature=0.92,
                            max_tokens=180,
                        )
                    result = _clean(response.choices[0].message.content or "")
                except Exception:
                    result = ""
            if not result or _looks_revealing(result):
                result = _local_fallback(raw, key)
            fp = _fingerprint(result)
            if fp in _HISTORY[key]:
                result = _local_fallback(raw, f"{key}:{len(_HISTORY[key]) + 1}")
                fp = _fingerprint(result)
            _HISTORY[key].append(fp)
            return result


voice = SocialVoice()
