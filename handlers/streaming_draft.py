"""Small Telegram draft-stream adapter for Oracle's future real token stream.

This module deliberately does not call the model. It only owns Telegram's
private-chat draft lifecycle, batching and local rate limiting. The existing
complete-response path remains untouched until the generator exposes a real
async token stream.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any


class TelegramDraftStream:
    """Publish partial text through Bot API sendMessageDraft safely.

    Telegram draft streaming is private-chat only. Updates are throttled by
    both time and character growth so a fast model cannot flood the Bot API.
    """

    MIN_INTERVAL = 0.85
    MIN_CHARS = 24
    MAX_TEXT = 4096

    def __init__(self, bot: Any, chat_id: int, draft_id: int, message_thread_id: int | None = None) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.draft_id = draft_id or 1
        self.message_thread_id = message_thread_id
        self._last_sent = 0.0
        self._last_text = ""
        self._lock = asyncio.Lock()

    async def _post(self, text: str, *, can_stop: bool = False) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "draft_id": self.draft_id,
            "text": text[: self.MAX_TEXT],
        }
        if self.message_thread_id is not None:
            payload["message_thread_id"] = self.message_thread_id
        if can_stop:
            payload["can_stop"] = True

        # python-telegram-bot 22.x exposes Bot._post internally while the
        # generated public method may lag a newly-added Bot API endpoint.
        post = getattr(self.bot, "_post", None)
        if post is None:
            raise RuntimeError("Telegram Bot API draft transport is unavailable")
        result = await post("sendMessageDraft", data=payload)
        self._last_sent = time.monotonic()
        self._last_text = text[: self.MAX_TEXT]
        return bool(result)

    async def thinking(self) -> bool:
        """Show a valid visible native Telegram thinking placeholder."""
        async with self._lock:
            return await self._post("Thinking…", can_stop=True)

    async def push(self, text: str, *, force: bool = False) -> bool:
        """Publish a new partial response when batching thresholds permit."""
        clean = (text or "").strip()
        if not clean:
            return False
        async with self._lock:
            grown = len(clean) - len(self._last_text)
            elapsed = time.monotonic() - self._last_sent
            if not force and grown < self.MIN_CHARS and elapsed < self.MIN_INTERVAL:
                return False
            return await self._post(clean)

    async def finish(self) -> None:
        """No-op marker: the caller must persist the final response normally."""
        return None
