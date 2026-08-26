"""Midnight AI service using Google's current async GenAI client."""
from __future__ import annotations

import asyncio
import logging
import os

from google import genai

log = logging.getLogger("midnight.ai")


class AIUnavailable(RuntimeError):
    pass


class AIService:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
        self._client: genai.Client | None = None
        self._lock = asyncio.Lock()

    def configured(self) -> bool:
        return bool(self.api_key)

    async def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise AIUnavailable("GEMINI_API_KEY is not configured")
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate(self, prompt: str, *, system_instruction: str | None = None, timeout: float = 20.0) -> str:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        client = await self._get_client()
        config = {"system_instruction": system_instruction} if system_instruction else None
        try:
            async def call():
                return await client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
            response = await asyncio.wait_for(call(), timeout=timeout)
            text = getattr(response, "text", None)
            if not text:
                raise AIUnavailable("Gemini returned an empty response")
            return text.strip()
        except asyncio.TimeoutError as exc:
            raise AIUnavailable("Gemini request timed out") from exc
        except Exception as exc:
            log.warning("AI generation failed: %s", type(exc).__name__)
            raise AIUnavailable("Gemini request failed") from exc


service = AIService()
