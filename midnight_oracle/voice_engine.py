"""Midnight Oracle voice-note engine.

Voice is an optional response modality. Midnight keeps one original female voice
identity while varying the spoken wording and delivery instructions naturally.
"""
from __future__ import annotations

import hashlib
import io
import random
import time
from dataclasses import dataclass

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY


@dataclass(frozen=True, slots=True)
class VoiceDecision:
    should_send: bool
    reason: str


VOICE_PROFILE = {
    "name": "midnight_original_female",
    "voice": "alloy",
    "style": "natural conversational female voice; warm, expressive, intimate but not theatrical; human-like pauses and varied emphasis; Indian-English/Hinglish friendly; never imitate or impersonate a real person",
}


class VoiceEngine:
    """Generate short, varied, deduplicated Telegram voice notes."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or OPENAI_API_KEY or "").strip()
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self._recent: dict[str, tuple[float, str]] = {}
        self._last_chat: dict[int, float] = {}
        self._daily_count: dict[int, tuple[int, int]] = {}

    def decide(self, *, chat_id: int, user_id: int, text: str, direct: bool, private: bool) -> VoiceDecision:
        if not self.client or not text.strip():
            return VoiceDecision(False, "voice_unconfigured")
        now = time.time()
        if now - self._last_chat.get(chat_id, 0.0) < 900:
            return VoiceDecision(False, "chat_cooldown")
        day = int(now // 86400)
        stored_day, count = self._daily_count.get(chat_id, (day, 0))
        if stored_day != day:
            count = 0
        if count >= 4:
            return VoiceDecision(False, "daily_cap")
        low = text.casefold()
        high_value = any(token in low for token in (
            "😭", "😂", "haha", "lol", "love", "sorry", "miss", "good night",
            "good morning", "congrats", "congratulations", "voice", "say it",
            "bol", "bolo", "sun", "suno", "feel", "feeling", "secret",
        ))
        emotional = any(token in low for token in ("🥺", "❤️", "🖤", "💔", "😂", "😭", "😌", "😏"))
        if not (direct or private or high_value or emotional):
            return VoiceDecision(False, "low_voice_value")
        probability = 0.34 if (direct or private) else 0.16
        if emotional:
            probability += 0.10
        if random.random() >= probability:
            return VoiceDecision(False, "oracle_chose_text")
        key = f"{chat_id}:{user_id}"
        digest = hashlib.sha256(text.strip().casefold().encode("utf-8")).hexdigest()
        previous = self._recent.get(key)
        if previous and previous[1] == digest and now - previous[0] < 86400:
            return VoiceDecision(False, "duplicate")
        return VoiceDecision(True, "oracle_chose_voice")

    @staticmethod
    def _clean_script(text: str, max_chars: int = 700) -> str:
        text = " ".join(text.split()).strip()
        return text[:max_chars].rstrip() if len(text) > max_chars else text

    @staticmethod
    def _delivery_style() -> str:
        return random.choice((
            "conversational, relaxed pacing, a tiny natural pause where appropriate",
            "warm and lightly playful, varied emphasis, unhurried delivery",
            "soft and reassuring, natural pauses, emotionally sincere",
            "bright and spontaneous, conversational rhythm, avoid announcer cadence",
        ))

    async def synthesize(self, text: str, *, voice: str | None = None) -> io.BytesIO | None:
        """Return an Opus audio buffer suitable for Telegram send_voice."""
        if not self.client:
            return None
        script = self._clean_script(text)
        if not script:
            return None
        try:
            response = await self.client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=voice or VOICE_PROFILE["voice"],
                input=script,
                response_format="opus",
                instructions=(VOICE_PROFILE["style"] + ". " + self._delivery_style()),
            )
            content = getattr(response, "content", None)
            if not content:
                return None
            audio = io.BytesIO(content)
            audio.name = "midnight-oracle.ogg"
            audio.seek(0)
            return audio
        except Exception:
            return None

    def record(self, chat_id: int, user_id: int, text: str) -> None:
        now = time.time()
        key = f"{chat_id}:{user_id}"
        digest = hashlib.sha256(text.strip().casefold().encode("utf-8")).hexdigest()
        self._recent[key] = (now, digest)
        day = int(now // 86400)
        stored_day, count = self._daily_count.get(chat_id, (day, 0))
        if stored_day != day:
            count = 0
        self._daily_count[chat_id] = (day, count + 1)
        self._last_chat[chat_id] = now
