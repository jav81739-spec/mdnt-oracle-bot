"""Main message router: preserve Phase 1 flow while adding Phase 2 social observation."""
from __future__ import annotations
import logging
from datetime import datetime
from telegram import Update, ReactionTypeEmoji
from telegram.ext import ContextTypes
from ..friend_engine import FriendEngine, GroupContext
from ..memory_engine import MemoryEngine
from ..mood_engine import MoodEngine
from ..generators.reply_generator import ReplyGenerator
from ..database import now_ts
from ..engines.joke_engine import JokeEngine
from ..engines.group_identity_engine import GroupIdentityEngine
from ..handlers.sticker_handler import StickerHandler

log = logging.getLogger("midnight.message_router")


class MessageRouter:
    """Coordinate direct summons, ambient friendship, memory, jokes, identity, and media."""

    def __init__(
        self,
        engine: FriendEngine,
        memory: MemoryEngine,
        mood: MoodEngine,
        replies: ReplyGenerator | None = None,
    ) -> None:
        """Bind social engines when the supplied Phase 1 engine exposes persistence."""
        self.engine = engine
        self.memory = memory
        self.mood = mood
        self.replies = replies or ReplyGenerator()
        self.recent: dict = {}
        db = getattr(engine, 'db', None)
        self.jokes = JokeEngine(db) if db else None
        self.identity = GroupIdentityEngine(db) if db else None
        self.stickers = StickerHandler(db) if db else None

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process one group text update and log any internal exceptions."""
        try:
            message = update.effective_message
            chat = update.effective_chat
            user = update.effective_user

            if not message or not chat or not user:
                return
            if chat.type not in {'group', 'supergroup'}:
                return

            text = (message.text or message.caption or '').strip()
            if not text or text.startswith('/'):
                return

            db = getattr(self.engine, 'db', None)
            if not db:
                log.error("MessageRouter: db is None — _post_init likely failed")
                return

            await db.execute(
                "INSERT INTO group_profile(group_id,group_name,timezone,created_at) VALUES(?,?,?,?) "
                "ON CONFLICT(group_id) DO UPDATE SET group_name=excluded.group_name",
                (chat.id, chat.title or '', 'Asia/Kolkata', now_ts()),
            )
            await db.upsert_member(user.id, chat.id, user.username or '', user.first_name or 'friend')

            profile = await self.memory.get(user.id, chat.id)
            recent = self.recent.setdefault(chat.id, [])
            now = datetime.now()
            signal = self.mood.estimate(text)

            ctx = GroupContext(
                str(user.id),
                str(chat.id),
                recent[-10:],
                now.hour,
                now.hour >= 23 or now.hour < 3,
                chat.title or '',
                profile.relationship_tier,
                profile.preferred_name or user.first_name or 'friend',
                now_ts(),
                (' | '.join(list(profile.themes[:2]) + list(profile.worries[:1]))) or 'none',
            )

            if self.jokes:
                await self.jokes.observe(text, user.id, chat.id)
            if self.identity:
                await self.identity.update(chat.id, text, signal)

            if self._is_direct_summon(text, context):
                reply = await self.replies.generate(
                    chat.title or 'Midnight Oracle',
                    ctx.sender_name,
                    ctx.relationship_tier,
                    text,
                    signal.summary(),
                    str(ctx.hour),
                    ctx.is_late_night,
                    ctx.memory_snippet,
                )
                await message.reply_text(reply)
                await self.memory.observe(user.id, chat.id, ctx.sender_name, text, True)
                return

            if self.stickers:
                media = await self.stickers.evaluate(message, signal, ctx)
                if
