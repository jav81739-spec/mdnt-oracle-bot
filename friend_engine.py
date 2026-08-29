"""Ambient social decision engine for Midnight Oracle.

The engine is deliberately dependency-free and synchronous. It observes short-lived
social context, applies conservative engagement rules, and returns a short original
reply only when the bot has a genuine conversational opening.
"""
from __future__ import annotations

import random
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque


@dataclass(frozen=True)
class _Signal:
    """Describe one detected social signal and its conversational weight."""

    name: str
    score: int


class FriendEngine:
    """Make low-noise ambient social engagement decisions for group chats."""

    TIRED = (
        "thak gaya", "thak gya", "thak gayi", "tired", "exhausted",
        "neend aa rahi", "bahut mehnat", "bohot mehnat", "worked all day",
        "so tired", "burnt out", "burned out", "drained",
    )
    FRUSTRATED = (
        "kya bakwas", "irritating", "fed up", "kuch nahi ho raha",
        "kuch nhi ho raha", "frustrated", "annoying", "dimag kharab",
        "pak gaya", "pak gayi", "can't deal", "cant deal",
    )
    LONELY = (
        "koi nahi", "akela", "akeli", "bore ho raha", "bore ho rahi",
        "lonely", "alone", "nobody", "koi baat nahi karta", "no one",
    )
    CELEBRATION = (
        "ho gaya bhai", "ho gaya", "finally", "khatam hua", "khatam ho gaya",
        "done", "finished", "we did it", "yes", "yess", "yesss", "let's go",
        "lets go", "mil gaya", "mil gayi", "pass ho gaya", "sorted",
    )
    WARMTH = (
        "haha", "hahaha", "lol", "lmao", "😂", "🤣", "😭", "chai", "coffee",
        "coffee?", "chai?", "bro", "bhai", "yaar", "lolz",
    )

    _TIRED_REPLIES = (
        "Aaj ka quota ho gaya bhai… thoda sa rest bhi deserve karta hai tu. 🌙",
        "Itna push kiya hai toh ab brain ko bhi logout karne de. 😭☕",
        "Bas ab khud pe overtime mat laga… rest le. 🌙",
    )
    _FRUSTRATED_REPLIES = (
        "Haan, woh wali frustration samajh aa rahi hai… bol, kya atka?",
        "Yeh clearly dimaag kha raha hai 😭 bol kya hua.",
        "Aaj patience ne resignation de diya lagta hai. 😂 Kya scene hai?",
    )
    _LONELY_REPLIES = (
        "Arre, room khaali ho toh baat kar lete hain. Kya chal raha hai? 🌙",
        "Boredom ko aaj thoda disturb karte hain. Bata, kya mood hai?",
        "Koi nahi? Abhi toh main sun raha hoon. Bol. ☾",
    )
    _CELEBRATION_REPLIES = (
        "AYE, finally. 😭🔥 Kya hua — spill.",
        "There we go. 😌 Ab bata, victory kis baat ki hai?",
        "Knew that ‘finally’ had a story behind it. 👀",
    )
    _WARM_REPLIES = (
        "😂 Okay, that was actually funny.",
        "Haan bhai, ab baat bani. 😭",
        "Chai/coffee mention detected. Priorities are correct. ☕",
    )

    def __init__(self, seed: int | None = None) -> None:
        """Initialize isolated in-memory cooldown state for this process."""
        self._rng = random.Random(seed)
        self._last_reply_by_group: dict[str, float] = {}
        self._last_sender_by_group: dict[str, str] = {}
        self._hourly_replies: dict[str, Deque[float]] = defaultdict(deque)

    def should_engage(self, message: str, context: dict) -> tuple[bool, str | None]:
        """Return whether Oracle should answer an ambient social message."""
        text = (message or "").strip()
        if not text:
            return False, None

        sender = str(context.get("sender", ""))
        group_id = str(context.get("group_id", ""))
        now = float(context.get("now", time.time()))
        cooldown = max(0.0, float(context.get("social_cooldown_seconds", 20 * 60)))
        recent = [str(x) for x in context.get("recent_messages", []) if x]
        recent_lower = " ".join(recent).lower()

        last_reply = self._last_reply_by_group.get(group_id, 0.0)
        if now - last_reply < cooldown:
            return False, None
        if self._last_sender_by_group.get(group_id) == sender:
            return False, None

        bucket = self._hourly_replies[group_id]
        while bucket and now - bucket[0] >= 3600:
            bucket.popleft()
        if len(bucket) >= 2:
            return False, None

        signals = self._signals(text)
        score = 0
        if any(s.name == "venting" for s in signals):
            score += 3
        if any(s.name == "celebration" for s in signals):
            score += 3
        if self._directed_outward(text, recent):
            score += 2
        if any(s.name == "warmth" for s in signals) or self._humor_opening(text, recent_lower):
            score += 2

        if score < 5:
            return False, None

        # Ambient engagement is probabilistic. Explicit summons never enter this class.
        rate = float(context.get("ambient_engagement_rate", 0.30))
        if self._rng.random() > max(0.0, min(1.0, rate)):
            return False, None

        reply = self._reply_for(text, signals, bool(context.get("is_late_night", False)))
        self._last_reply_by_group[group_id] = now
        self._last_sender_by_group[group_id] = sender
        bucket.append(now)
        return True, reply

    def _signals(self, text: str) -> list[_Signal]:
        """Detect the supported emotional and warmth signals in text."""
        normalized = self._normalize(text)
        found: list[_Signal] = []
        if self._contains(normalized, self.TIRED):
            found.append(_Signal("tired", 3))
            found.append(_Signal("venting", 3))
        if self._contains(normalized, self.FRUSTRATED):
            found.append(_Signal("frustrated", 3))
            found.append(_Signal("venting", 3))
        if self._contains(normalized, self.LONELY):
            found.append(_Signal("lonely", 3))
            found.append(_Signal("venting", 3))
        if self._contains(normalized, self.CELEBRATION):
            found.append(_Signal("celebration", 3))
        if self._contains(normalized, self.WARMTH):
            found.append(_Signal("warmth", 2))
        return found

    def _reply_for(self, text: str, signals: list[_Signal], late: bool) -> str:
        """Select a short original reply matched to the strongest social signal."""
        names = {s.name for s in signals}
        if "tired" in names:
            pool = self._TIRED_REPLIES
        elif "frustrated" in names:
            pool = self._FRUSTRATED_REPLIES
        elif "lonely" in names:
            pool = self._LONELY_REPLIES
        elif "celebration" in names:
            pool = self._CELEBRATION_REPLIES
        else:
            pool = self._WARM_REPLIES
        reply = self._rng.choice(pool)
        if late and reply.endswith("."):
            return reply[:-1] + "… 🌙"
        return reply

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize punctuation and whitespace while preserving emoji."""
        return re.sub(r"\s+", " ", text.casefold()).strip()

    @staticmethod
    def _contains(text: str, phrases: tuple[str, ...]) -> bool:
        """Return whether any phrase appears as a word-aware substring."""
        return any(phrase in text for phrase in phrases)

    @staticmethod
    def _directed_outward(text: str, recent: list[str]) -> bool:
        """Estimate whether the message opens a social response rather than being a bare thought."""
        low = text.casefold()
        if "?" in text or any(x in low.split() for x in ("bhai", "bro", "yaar", "guys", "someone", "anyone")):
            return True
        if len(text.split()) >= 5:
            return True
        return bool(recent and text != recent[-1])

    @staticmethod
    def _humor_opening(text: str, recent: str) -> bool:
        """Detect lightweight openings where a playful reply would fit."""
        low = text.casefold()
        return any(x in low for x in ("haha", "lol", "lmao", "😂", "🤣", "😭")) or "😂" in recent or "🤣" in recent
