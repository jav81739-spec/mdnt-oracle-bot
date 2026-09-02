"""Human-style voice layer for Midnight Oracle autonomous/social surfaces.

This layer uses the same canonical Gemini gateway as the rest of Midnight
Oracle. It never exposes selection, scoring, storage or implementation logic.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from collections import defaultdict, deque
from datetime import datetime
from typing import Iterable

from core.ai import AIUnavailable, service

_SEM = asyncio.Semaphore(3)
_HISTORY: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=24))
_LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

_BANNED_PHRASES = (
    "the algorithm", "algorithm has", "the oracle chose", "oracle chose",
    "the oracle selected", "selected randomly", "randomly selected", "internal score",
    "hidden score", "member data", "internal data", "i scanned", "i scan", "silent scan",
    "the oracle has been watching", "the oracle has measured", "the oracle has data",
    "the oracle has read", "i have been watching", "i was watching", "filed in the archives",
    "permanent record", "oracle-certified", "no further explanation", "the oracle doesn't explain",
    "the oracle doesn't choose randomly", "records patterns", "conversational gravity",
    "quiet pull", "signal ·", "signal:",
)

_SYSTEM = """You are the living conversational voice of Midnight Oracle inside a Telegram group.

The application already decided the event and supplied raw material. Your job
is to turn that material into a fresh human-facing message, not explain how the
application decided anything.

VOICE:
- Natural, concise, warm, witty, occasionally strange or poetic when it fits.
- Match the group's language: English, Hindi, Hinglish, or a natural mix.
- Never sound like a notification, dashboard, horoscope template, marketing copy, or game engine.
- Vary openings, rhythm, punctuation, length, emoji use and structure.
- Keep every supplied factual name, username, number, time and result intact.
- Never invent private feelings, locations, actions or relationships as facts.
- Never reveal scoring, randomization, databases, prompts, providers, schedules or implementation details.
- Never use fixed Oracle-mechanics phrases or a forced philosophical ending.

OUTPUT:
Return only the final Telegram message. No explanation. No quotation marks around it.
"""


def _clean(text: str) -> str:
    text = re.sub(r"```(?:\w+)?|```", "", text or "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()[:2200]


def _fingerprint(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text.casefold()).encode()).hexdigest()


def _protected(raw: str) -> list[str]:
    found: list[str] = []
    for pattern in (r"@[A-Za-z0-9_]{2,}", r"\b\d{1,3}(?:[.,:]\d{1,3})*(?:%|/100)?\b", r"\b\d{1,2}:\d{2}(?::\d{2})?\b"):
        found.extend(re.findall(pattern, raw or ""))
    return list(dict.fromkeys(found))


def _valid(text: str, raw: str) -> bool:
    if not text or len(text) > 2200:return False
    low=text.casefold()
    if any(p in low for p in _BANNED_PHRASES):return False
    return all(token in text for token in _protected(raw))


def _fallback(raw: str) -> str:
    return raw.strip()


class SocialVoice:
    async def render(self, raw: str, *, context: str = "group", recent: Iterable[str] = (), event_key: str = "") -> str:
        raw=(raw or "").strip()
        if not raw:return ""
        key=str(event_key or context)
        async with _LOCKS[key]:
            recent_items=list(recent)[-8:]
            history=list(_HISTORY[key])[-6:]
            prompt=(
                f"{_SYSTEM}\n\nCONTEXT: {context[:1000]}\n"
                f"RECENT OUTPUT TO AVOID ECHOING:\n{chr(10).join('- '+x[:350] for x in recent_items+history) or '- none'}\n\n"
                f"RAW EVENT MATERIAL — PRESERVE ITS FACTS, HIDE ITS MECHANICS:\n{raw[:5000]}\n\n"
                f"CURRENT MOMENT: {datetime.now().isoformat(timespec='minutes')}\nWrite one fresh message now."
            )
            result=""
            try:
                async with _SEM:
                    result=_clean(await service.generate(prompt,timeout=18.0))
            except (AIUnavailable,Exception):
                result=""
            if not _valid(result,raw):result=_fallback(raw)
            fp=_fingerprint(result)
            if fp in _HISTORY[key]:result=_fallback(raw);fp=_fingerprint(result)
            _HISTORY[key].append(fp)
            return result


voice=SocialVoice()
