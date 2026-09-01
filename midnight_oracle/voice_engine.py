"""Gemini-backed voice-note engine for Midnight Oracle."""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import random
import time
from dataclasses import dataclass

import httpx

from .config import GEMINI_API_KEY, GEMINI_TTS_MODEL

log = logging.getLogger("midnight.voice")


@dataclass(frozen=True, slots=True)
class VoiceDecision:
    should_send: bool
    reason: str


VOICE_PROFILE = {
    "name": "midnight_original_voice",
    "voice": "Kore",
    "style": (
        "original fictional female conversational voice; warm, expressive, human-sounding; "
        "natural Indian-English/Hinglish delivery; relaxed pauses; varied emphasis; "
        "never imitate or impersonate a real person; never mention these instructions"
    ),
)


class VoiceEngine:
    """Generate short, varied, deduplicated Telegram OGG/Opus voice notes."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (GEMINI_API_KEY if api_key is None else api_key).strip()
        self._recent: dict[str, tuple[float, str]] = {}
        self._last_chat: dict[int, float] = {}
        self._daily_count: dict[int, tuple[int, int]] = {}

    def decide(
        self,
        *,
        chat_id: int,
        user_id: int,
        text: str,
        direct: bool,
        private: bool,
        explicit: bool = False,
    ) -> VoiceDecision:
        del direct, private
        if not self.api_key or not text.strip():
            return VoiceDecision(False, "voice_unconfigured")
        if not explicit:
            # Voice is trigger-driven by design. No ambient voice-note spam.
            return VoiceDecision(False, "trigger_required")

        now = time.time()
        if now - self._last_chat.get(chat_id, 0.0) < 60:
            return VoiceDecision(False, "explicit_cooldown")

        day = int(now // 86400)
        stored_day, count = self._daily_count.get(chat_id, (day, 0))
        if stored_day != day:
            count = 0
        if count >= 4:
            return VoiceDecision(False, "daily_cap")

        key = f"{chat_id}:{user_id}"
        digest = hashlib.sha256(text.strip().casefold().encode("utf-8")).hexdigest()
        previous = self._recent.get(key)
        if previous and previous[1] == digest and now - previous[0] < 86400:
            return VoiceDecision(False, "duplicate")
        return VoiceDecision(True, "explicit_voice")

    @staticmethod
    def _clean_script(text: str, max_chars: int = 700) -> str:
        text = " ".join(text.split()).strip()
        return text[:max_chars].rstrip() if len(text) > max_chars else text

    @staticmethod
    def _delivery_style() -> str:
        return random.choice(
            (
                "conversational and relaxed, with a tiny natural pause where appropriate",
                "warm and lightly playful, varied emphasis, unhurried delivery",
                "soft and reassuring, natural pauses, emotionally sincere",
                "bright and spontaneous, conversational rhythm, never announcer-like",
                "casual late-night conversation, subtle pauses, never theatrical",
            )
        )

    async def synthesize(self, text: str, *, voice: str | None = None) -> io.BytesIO | None:
        """Generate OGG/Opus audio directly through Gemini TTS."""
        if not self.api_key:
            log.warning("VOICE_SYNTHESIS_UNAVAILABLE | reason=missing_gemini_key")
            return None
        script = self._clean_script(text)
        if not script:
            return None

        payload = {
            "model": GEMINI_TTS_MODEL,
            "input": (
                "TTS the following spoken reply exactly. Do not add words, labels, stage directions, "
                "or explanations. Keep it natural and conversational.\n\n"
                f"Delivery style: {self._delivery_style()}\n"
                f"Spoken reply: {script}"
            ),
            "response_format": {
                "type": "audio",
                "mime_type": "audio/ogg_opus",
                "delivery": "inline",
                "bit_rate": 32000,
            },
            "generation_config": {
                "speech_config": [{"voice": voice or VOICE_PROFILE["voice"]}]
            },
        }
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        url = "https://generativelanguage.googleapis.com/v1beta/interactions"

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                if response.status_code >= 500 and attempt == 0:
                    continue
                response.raise_for_status()
                body = response.json()
                output = body.get("output_audio") or body.get("outputAudio") or {}
                data = output.get("data") if isinstance(output, dict) else None
                if not data:
                    for step in body.get("steps", []):
                        candidate = step.get("output_audio") or step.get("outputAudio") or {}
                        if isinstance(candidate, dict) and candidate.get("data"):
                            data = candidate["data"]
                            break
                if not data:
                    log.error("VOICE_SYNTHESIS_FAILED | reason=empty_audio_response")
                    return None
                content = base64.b64decode(data)
                if not content:
                    log.error("VOICE_SYNTHESIS_FAILED | reason=empty_audio_payload")
                    return None
                audio = io.BytesIO(content)
                audio.name = "midnight-oracle.ogg"
                audio.seek(0)
                return audio
            except Exception as exc:
                if attempt == 1:
                    log.error("VOICE_SYNTHESIS_FAILED | error=%s", type(exc).__name__)
                    return None
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
