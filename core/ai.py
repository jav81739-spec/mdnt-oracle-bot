"""Central Gemini HTTPS gateway for Midnight Oracle."""
from __future__ import annotations
import asyncio, os
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

    def __post_init__(self):
        self.api_key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        configured = os.getenv("GEMINI_MODEL", "").strip()
        retired = {"gemini-2.0-flash", "gemini-3.5-flash-lite"}
        self.model = self.model or (configured if configured and configured not in retired else "gemini-3.7-flash")
        self._client = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self):
        if self._client is not None: return self._client
        async with self._client_lock:
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=min(5.0, self.timeout)), headers={"Content-Type":"application/json","x-goog-api-key":self.api_key})
        return self._client

    async def close(self):
        async with self._client_lock:
            client, self._client = self._client, None
            if client: await client.aclose()

    async def generate(self, prompt: str, *, timeout: float | None = None) -> str:
        if not self.api_key: raise AIUnavailable("provider unavailable")
        if not prompt.strip(): raise AIUnavailable("empty prompt")
        client = await self._get_client()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {"contents":[{"role":"user","parts":[{"text":prompt[:12000]}]}],"generationConfig":{"maxOutputTokens":300}}
        last = None
        for attempt in range(self.retries + 1):
            response = None
            try:
                response = await client.post(url, json=payload, timeout=timeout or self.timeout)
                if response.status_code == 404:
                    raise AIUnavailable("provider unavailable")
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                elif response.status_code >= 400:
                    raise AIUnavailable("provider unavailable")
                text = self._extract_text(response.json())
                if text: return text.strip()
                raise AIUnavailable("empty provider response")
            except AIUnavailable as exc:
                last = exc
                if response is not None and response.status_code == 404: break
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
            if attempt < self.retries: await asyncio.sleep(0.25 * (2 ** attempt))
        raise AIUnavailable("provider unavailable") from last

    @staticmethod
    def _extract_text(data):
        candidates = data.get("candidates") or []
        if not candidates: return ""
        parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        return "".join(str(p.get("text","")) for p in parts if isinstance(p,dict))

service = AIService()
