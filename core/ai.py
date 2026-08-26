"""Central Gemini gateway for Midnight Oracle.

Uses Google's HTTPS generateContent endpoint directly so the Telegram runtime
can keep its supported httpx dependency range while all AI calls pass through
one service boundary.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import httpx


class AIUnavailable(RuntimeError):
    """Raised when Gemini cannot produce a response within the retry budget."""


@dataclass
class AIService:
    api_key: str = ""
    model: str = ""
    timeout: float = 25.0
    retries: int = 2

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = self.model or os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=min(5.0, self.timeout)),
                headers={
                    "Content-Type": "application/json",
                    # Keep the API key in the request header rather than the URL,
                    # preventing accidental leakage through proxy/access logs.
                    "x-goog-api-key": self.api_key,
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def generate(self, prompt: str, *, timeout: float | None = None) -> str:
        if not self.api_key:
            raise AIUnavailable("GEMINI_API_KEY is not configured")
        if not prompt or not prompt.strip():
            raise AIUnavailable("empty AI prompt")

        client = await self._get_client()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt[:12000]}]}]}
        request_timeout = timeout or self.timeout
        last: Exception | None = None

        for attempt in range(self.retries + 1):
            try:
                response = await client.post(url, json=payload, timeout=request_timeout)
                if response.status_code >= 400:
                    if response.status_code != 429 and response.status_code < 500:
                        raise AIUnavailable(f"Gemini API returned HTTP {response.status_code}")
                    response.raise_for_status()
                data = response.json()
                text = self._extract_text(data)
                if not text:
                    raise AIUnavailable("Gemini returned no text candidate")
                return text.strip()
            except (httpx.HTTPError, ValueError, AIUnavailable) as exc:
                last = exc
                if attempt >= self.retries:
                    break
                await asyncio.sleep(0.25 * (2 ** attempt))

        raise AIUnavailable("Gemini request failed after retries") from last

    @staticmethod
    def _extract_text(data: dict) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        return "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))


service = AIService()
