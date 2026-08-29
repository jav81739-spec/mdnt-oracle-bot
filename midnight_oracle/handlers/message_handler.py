"""Main Telegram message router for the standalone Phase 1 architecture."""
from __future__ import annotations
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from ..friend_engine import FriendEngine, GroupContext
from ..memory_engine import MemoryEngine
from ..mood_engine import MoodEngine
from ..generators.reply_generator import ReplyGenerator
from ..database import now_ts


class MessageRouter:
    """Coordinate direct summons, ambient friendship, memory observation, and command exclusion."""

    def __init__(self, engine: FriendEngine, memory: MemoryEngine, mood: MoodEngine, replies: ReplyGenerator | None = None) -> None:
        """Bind the message router to its engines."""
        self.engine, self.memory, self.mood = engine, memory, mood
        self.replies = replies or ReplyGenerator()
        self.recent: dict[int, list[str]] = {}

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process one Telegram message without ever leaking internal exceptions."""
        try:
            message = update.effective_message; chat = update.effective_chat; user = update.effective_user
            if not message or not chat or not user or chat.type not in {"group", "supergroup"}: return
            text = (message.text or message.caption or "").strip()
            if not text or text.startswith("/"): return
            await self.engine.db.execute("""INSERT INTO group_profile(group_id,group_name,timezone,created_at) VALUES(?,?,?,?)
            ON CONFLICT(group_id) DO UPDATE SET group_name=excluded.group_name""", (chat.id, chat.title or "", str(context.application.bot_data.get("oracle_timezone", "Asia/Kolkata")), now_ts()))
            recent = self.recent.setdefault(chat.id, [])
            ctx = GroupContext(str(user.id), str(chat.id), recent[-10:], datetime.now().hour, datetime.now().hour >= 23 or datetime.now().hour < 3, chat.title or "", "new", user.first_name or "friend")
            direct = self._is_direct_summon(text, context)
            if direct:
                reply = await self.replies.generate(chat.title or "Midnight Oracle", user.first_name or "friend", "new", text, self.mood.group_mood(chat.id).summary(), str(ctx.hour), ctx.is_late_night, "none")
                await message.reply_text(reply); return
            decision = await self.engine.process_message(message, ctx)
            self.mood.observe(user.id, chat.id, text)
            await self.memory.observe(user.id, chat.id, user.first_name or "friend", text, decision.should_reply or self.mood.estimate(text).social >= .5)
            recent.append(text); del recent[:-10]
            if decision.should_reply and decision.reply_text: await message.reply_text(decision.reply_text)
        except Exception:
            return

    @staticmethod
    def _is_direct_summon(text: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Detect explicit Oracle summons without using ambient scoring."""
        low = text.casefold(); username = str(getattr(getattr(context, "bot", None), "username", "") or "").casefold()
        return "oracle" in low or "midnight" in low or (username and f"@{username}" in low)
