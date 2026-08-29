"""Central Gemini HTTPS gateway for Midnight Oracle."""
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
    timeout: float = 20.0
    retries: int = 2

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = self.model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout, connect=min(5.0, self.timeout)),
                    headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                )
        return self._client

    async def close(self) -> None:
        async with self._client_lock:
            client, self._client = self._client, None
            if client is not None:
                await client.aclose()

    async def generate(self, prompt: str, *, timeout: float | None = None) -> str:
        if not self.api_key:
            raise AIUnavailable("GEMINI_API_KEY is not configured")
        if not prompt or not prompt.strip():
            raise AIUnavailable("empty AI prompt")

        client = await self._get_client()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt[:12000]}]}],
            "generationConfig": {"maxOutputTokens": 300},
        }
        request_timeout = timeout or self.timeout
        last: Exception | None = None

        for attempt in range(self.retries + 1):
            response = None
            try:
                response = await client.post(url, json=payload, timeout=request_timeout)
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                elif response.status_code >= 400:
                    raise AIUnavailable(f"Gemini API returned HTTP {response.status_code}")
                text = self._extract_text(response.json())
                if not text:
                    raise AIUnavailable("Gemini returned no text candidate")
                return text.strip()
            except AIUnavailable as exc:
                last = exc
                if response is not None and response.status_code < 500 and response.status_code != 429:
                    break
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
            if attempt < self.retries:
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
