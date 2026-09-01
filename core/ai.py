"""Central Gemini HTTPS gateway for Midnight Oracle."""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import httpx


class AIUnavailable(RuntimeError):
    """Provider unavailable; callers must switch to the local chat path."""


@dataclass
class AIService:
    api_key: str = ""
    model: str = ""
    timeout: float = 20.0
    retries: int = 2

    DEFAULT_MODEL = "gemini-3.7-flash"
    FALLBACK_MODELS = (
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    )
    RETIRED_MODELS = {
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-lite-001",
        "gemini-3.5-flash-lite",
    }

    def __post_init__(self):
        self.api_key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        configured = os.getenv("GEMINI_MODEL", "").strip()
        if configured and configured not in self.RETIRED_MODELS:
            self.model = self.model or configured
        else:
            self.model = self.model or self.DEFAULT_MODEL
        self._client = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self):
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout, connect=min(5.0, self.timeout)),
                    headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                )
        return self._client

    async def close(self):
        async with self._client_lock:
            client, self._client = self._client, None
            if client:
                await client.aclose()

    async def _discover_model(self, client) -> str | None:
        """Select a currently exposed generateContent model after a 404."""
        try:
            response = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"pageSize": 100},
                timeout=min(8.0, self.timeout),
            )
            response.raise_for_status()
            models = response.json().get("models") or []
            available = {
                str(item.get("name", "")).removeprefix("models/")
                for item in models
                if "generateContent" in (item.get("supportedGenerationMethods") or [])
            }
            for candidate in self.FALLBACK_MODELS:
                if candidate in available:
                    return candidate
            preferred = sorted(name for name in available if "flash" in name and "preview" not in name)
            return preferred[0] if preferred else None
        except Exception:
            return None

    async def generate(self, prompt: str, *, timeout: float | None = None) -> str:
        if not self.api_key:
            raise AIUnavailable("provider unavailable")
        if not prompt.strip():
            raise AIUnavailable("empty prompt")
        client = await self._get_client()
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt[:12000]}]}],
            "generationConfig": {"maxOutputTokens": 300},
        }
        last = None
        for attempt in range(self.retries + 1):
            response = None
            try:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                    json=payload,
                    timeout=timeout or self.timeout,
                )
                if response.status_code == 404:
                    discovered = await self._discover_model(client)
                    if discovered and discovered != self.model:
                        self.model = discovered
                        response = await client.post(
                            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                            json=payload,
                            timeout=timeout or self.timeout,
                        )
                    if response.status_code == 404:
                        raise AIUnavailable("provider unavailable")
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                elif response.status_code >= 400:
                    raise AIUnavailable("provider unavailable")
                text = self._extract_text(response.json())
                if text:
                    return text.strip()
                raise AIUnavailable("empty provider response")
            except AIUnavailable as exc:
                last = exc
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
            if attempt < self.retries:
                await asyncio.sleep(0.25 * (2 ** attempt))
        raise AIUnavailable("provider unavailable") from last

    @staticmethod
    def _extract_text(data):
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        return "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))


service = AIService()
