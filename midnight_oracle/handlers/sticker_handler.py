"""Explicit-only Telegram sticker/reaction handling."""
from __future__ import annotations

from dataclasses import dataclass

from ..database import Database, now_ts
from ..data.sticker_map import STICKER_CONTEXTS


@dataclass(slots=True)
class StickerDecision:
    """Describe whether an explicitly requested media action should be sent."""
    should_send: bool
    sticker_id: str | None
    reaction_emoji: str | None


class StickerHandler:
    """Keep stickers out of ordinary conversation unless explicitly requested."""

    _REQUESTS = (
        "send sticker",
        "send me a sticker",
        "sticker bhejo",
        "sticker bhej",
        "sticker please",
        "sticker pls",
    )

    def __init__(self, db: Database) -> None:
        self.db = db

    async def evaluate(self, message: object, mood: object, context: object) -> StickerDecision:
        """Return media only for an explicit sticker request; never hijack a reply."""
        del mood
        try:
            text = str(getattr(message, 'text', None) or '').casefold().strip()
            if not text or not any(request in text for request in self._REQUESTS):
                return StickerDecision(False, None, None)
            rows = await self.db.fetchall(
                "SELECT COUNT(*) FROM sticker_events WHERE group_id=? AND sent_at>?",
                (int(context.group_id), now_ts() - 3600),
            )
            if int(rows[0][0]) >= 1:
                return StickerDecision(False, None, None)
            item = STICKER_CONTEXTS.get('something_ridiculous')
            if not item:
                return StickerDecision(False, None, None)
            return StickerDecision(
                bool(item.get('sticker_id')),
                item.get('sticker_id'),
                item.get('emoji') if not item.get('sticker_id') else None,
            )
        except Exception:
            return StickerDecision(False, None, None)

    async def record(self, group_id: int, context_name: str, sticker_id: str | None) -> None:
        await self.db.execute(
            "INSERT INTO sticker_events(group_id,trigger_context,sticker_id,sent_at) VALUES(?,?,?,?)",
            (group_id, context_name, sticker_id, now_ts()),
        )
