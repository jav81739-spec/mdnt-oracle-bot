"""Explicit-only Telegram sticker/reaction handling."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..database import Database, now_ts
from ..data.sticker_map import STICKER_CONTEXTS


@dataclass(slots=True)
class StickerDecision:
    should_send: bool
    sticker_id: str | None
    reaction_emoji: str | None


class StickerHandler:
    """Keep stickers out of ordinary conversation unless the member clearly asks."""

    _REQUEST = re.compile(r"^(?:please\s+)?(?:send(?:\s+me)?\s+)?sticker(?:\s+please|\s+pls)?[.!?\s]*$|^(?:send|bhej|bhejo)\s+(?:me\s+)?(?:a\s+)?sticker[.!?\s]*$", re.I)
    _NEGATIVE = re.compile(r"\b(?:don't|do not|dont|mat|nahi|nahin)\s+(?:send|bhej|bhejo)\b", re.I)

    def __init__(self, db: Database) -> None:
        self.db = db

    async def evaluate(self, message: object, mood: object, context: object) -> StickerDecision:
        del mood
        try:
            text = str(getattr(message, "text", None) or "").strip()
            if not text or self._NEGATIVE.search(text) or not self._REQUEST.fullmatch(text):
                return StickerDecision(False, None, None)
            rows = await self.db.fetchall(
                "SELECT COUNT(*) FROM sticker_events WHERE group_id=? AND sent_at>?",
                (int(context.group_id), now_ts() - 3600),
            )
            if int(rows[0][0]) >= 1:
                return StickerDecision(False, None, None)
            item = STICKER_CONTEXTS.get("something_ridiculous")
            if not item:
                return StickerDecision(False, None, None)
            return StickerDecision(bool(item.get("sticker_id")), item.get("sticker_id"), item.get("emoji") if not item.get("sticker_id") else None)
        except Exception:
            return StickerDecision(False, None, None)

    async def record(self, group_id: int, context_name: str, sticker_id: str | None) -> None:
        await self.db.execute(
            "INSERT INTO sticker_events(group_id,trigger_context,sticker_id,sent_at) VALUES(?,?,?,?)",
            (group_id, context_name, sticker_id, now_ts()),
        )
