"""Central Gemini gateway for Midnight Oracle.

Interactions API is the primary transport; the supported generateContent
transport remains a narrow compatibility fallback so provider migrations do
not take the bot offline.
"""
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
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    )
    RETIRED_MODELS = {
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-lite-001",
        "gemini-3.1-flash-lite-preview",
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
    }
    INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
    MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __post_init__(self):
        self.api_key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        configured = os.getenv("GEMINI_MODEL", "").strip()
        self.model = self.model or (configured if configured and configured not in self.RETIRED_MODELS else self.DEFAULT_MODEL)
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
        try:
            response = await client.get(self.MODELS_URL, params={"pageSize": 100}, timeout=min(8.0, self.timeout))
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

    async def _interactions(self, client, prompt: str, timeout: float) -> str:
        response = await client.post(
            self.INTERACTIONS_URL,
            json={"model": self.model, "input": prompt[:12000]},
            timeout=timeout,
        )
        if response.status_code >= 400:
            response.raise_for_status()
        text = self._extract_interaction_text(response.json())
        if not text:
            raise AIUnavailable("empty provider response")
        return text.strip()

    async def _legacy_generate_content(self, client, prompt: str, timeout: float) -> str:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt[:12000]}]}],
            "generationConfig": {"maxOutputTokens": 300},
        }
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            json=payload,
            timeout=timeout,
        )
        if response.status_code == 404:
            discovered = await self._discover_model(client)
            if discovered and discovered != self.model:
                self.model = discovered
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                    json=payload,
                    timeout=timeout,
                )
        if response.status_code >= 400:
            response.raise_for_status()
        text = self._extract_text(response.json())
        if not text:
            raise AIUnavailable("empty provider response")
        return text.strip()

    async def generate(self, prompt: str, *, timeout: float | None = None) -> str:
        if not self.api_key or not prompt.strip():
            raise AIUnavailable("provider unavailable")
        client = await self._get_client()
        request_timeout = timeout or self.timeout
        last = None
        for attempt in range(self.retries + 1):
            try:
                try:
                    return await self._interactions(client, prompt, request_timeout)
                except httpx.HTTPStatusError as exc:
                    # Interactions is the primary path. A 404/405/410 is a
                    # transport/model compatibility signal, not a user error.
                    if exc.response.status_code not in {404, 405, 410}:
                        raise
                    return await self._legacy_generate_content(client, prompt, request_timeout)
            except AIUnavailable as exc:
                last = exc
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
            if attempt < self.retries:
                await asyncio.sleep(0.25 * (2 ** attempt))
        raise AIUnavailable("provider unavailable") from last

    @staticmethod
    def _extract_interaction_text(data):
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text
        parts = []
        for step in data.get("steps") or []:
            if not isinstance(step, dict) or step.get("type") not in {"model_output", "output"}:
                continue
            content = step.get("content") or []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
        return "".join(parts)

    @staticmethod
    def _extract_text(data):
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        return "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))


service = AIService()
