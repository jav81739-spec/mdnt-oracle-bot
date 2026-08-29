"""Main Telegram message router for the standalone Phase 1 architecture."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from ..friend_engine import FriendEngine, GroupContext
from ..memory_engine import MemoryEngine
from ..mood_engine import MoodEngine


class MessageRouter:
    """Coordinate ambient friendship, memory observation, and command exclusion."""

    def __init__(self, engine: FriendEngine, memory: MemoryEngine, mood: MoodEngine) -> None:
        """Bind the message router to its engines."""
        self.engine, self.memory, self.mood = engine, memory, mood
        self.recent: dict[int, list[str]] = {}

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process one Telegram message without ever leaking internal exceptions."""
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if not message or not chat or not user or chat.type not in {"group", "supergroup"}:
            return
        text = (message.text or message.caption or "").strip()
        if not text or text.startswith("/"):
            return
        recent = self.recent.setdefault(chat.id, [])
        ctx = GroupContext(str(user.id), str(chat.id), recent[-10:], datetime.now().hour, datetime.now().hour >= 23 or datetime.now().hour < 3, chat.title or "", "new", user.first_name or "friend")
        decision = await self.engine.process_message(message, ctx)
        self.mood.observe(user.id, chat.id, text)
        await self.memory.observe(user.id, chat.id, user.first_name or "friend", text, decision.should_reply or self.mood.estimate(text).social >= .5)
        recent.append(text)
        del recent[:-10]
        if decision.should_reply and decision.reply_text:
            await message.reply_text(decision.reply_text)
