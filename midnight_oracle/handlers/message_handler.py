"""Canonical Midnight Oracle message router — one decision, one delivery."""
from __future__ import annotations

from datetime import datetime
import re

from telegram import ReactionTypeEmoji, Update
from telegram.ext import ContextTypes

from ..database import now_ts
from ..friend_engine import FriendEngine, GroupContext
from ..generators.reply_generator import ReplyGenerator
from ..handlers.sticker_handler import StickerHandler
from ..memory_engine import MemoryEngine
from ..mood_engine import MoodEngine
from ..voice_engine import VoiceEngine
from ..voice_triggers import wants_voice
from ..engines.group_identity_engine import GroupIdentityEngine
from ..engines.joke_engine import JokeEngine
from middleware.alert import soft_alert
from middleware.cooldown import cooldown_seconds, is_cooling
from middleware.recent_buffer import load_recent, save_recent


_CONTINUATION_RE = re.compile(
    r"^(?:more|more\s+please|tell\s+me\s+more|go\s+on|continue|keep\s+going|and\?|then\?|what\s+happened\s+next|aur\s+batao|aur\s+bata|aage\s+bolo|phir\s+what)\W*$",
    re.IGNORECASE,
)


def _message_text(message) -> str:
    """Extract visible text from a Telegram message without exposing internals."""
    return (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()


def _reply_context(message, bot_id: int | None) -> list[str]:
    """Recover the Oracle text behind a replied-to GIF/photo, including one reply hop."""
    target = getattr(message, "reply_to_message", None)
    if not target or not bot_id:
        return []
    target_user = getattr(target, "from_user", None)
    if getattr(target_user, "id", None) != bot_id:
        return []

    lines: list[str] = []
    target_text = _message_text(target)
    if target_text:
        lines.append(f"Oracle message being answered: {target_text[:1200]}")
    elif getattr(target, "animation", None) or getattr(target, "photo", None):
        lines.append("Oracle media message being answered: [visual companion]")

    original = getattr(target, "reply_to_message", None)
    original_user = getattr(original, "from_user", None)
    if original and getattr(original_user, "id", None) == bot_id:
        original_text = _message_text(original)
        if original_text:
            lines.append(f"Original Oracle message behind that media: {original_text[:1200]}")
    return lines


def _is_continuation_request(text: str) -> bool:
    """Recognise natural short follow-ups such as 'More' without hijacking normal chat."""
    return bool(_CONTINUATION_RE.fullmatch((text or "").strip()))


def _continuation_fallback(text: str) -> str:
    """Keep an obvious continuation turn alive if the provider is temporarily unavailable."""
    if _is_continuation_request(text):
        return "Haan — ruk, ussi baat ko thoda aur kholte hain. 🌙"
    return "Haan, bolo."


class MessageRouter:
    """Coordinate direct chat, conservative ambient chat, memory, media and voice."""

    def __init__(self, engine: FriendEngine, memory: MemoryEngine, mood: MoodEngine, replies: ReplyGenerator | None = None) -> None:
        self.engine = engine
        self.memory = memory
        self.mood = mood
        self.replies = replies or ReplyGenerator()
        self.recent: dict[int, list[str]] = {}
        db = getattr(engine, "db", None)
        self.jokes = JokeEngine(db) if db else None
        self.identity = GroupIdentityEngine(db) if db else None
        self.stickers = StickerHandler(db) if db else None
        self.voice = VoiceEngine()

    async def _reply(self, message, text: str, **kwargs):
        if not str(text or "").strip():
            return None
        return await message.reply_text(text, reply_to_message_id=message.message_id, **kwargs)

    async def _send_reply(self, message, reply: str, *, chat_id: int, user_id: int, text: str, direct: bool, private: bool) -> bool:
        """Deliver exactly one response. Voice is attempted only for explicit voice requests."""
        if not str(reply or "").strip():
            return False
        explicit = wants_voice(text)
        decision = self.voice.decide(chat_id=chat_id, user_id=user_id, text=text, direct=direct, private=private, explicit=explicit)
        if decision.should_send:
            audio = await self.voice.synthesize(reply)
            if audio is not None:
                try:
                    await message.reply_voice(voice=audio, reply_to_message_id=message.message_id)
                    self.voice.record(chat_id, user_id, reply)
                    return True
                except Exception as exc:
                    await soft_alert(None, "voice_delivery", exc)
                finally:
                    try:
                        audio.close()
                    except Exception:
                        pass
        await self._reply(message, reply)
        return True

    async def _announce_achievements(self, message, member, group_id, event) -> None:
        """Achievements never create a second unsolicited conversational message."""
        del message, member, group_id, event
        return

    async def _hidden_surprise(self, message, chat_id, user_id, text):
        """Inline surprise delivery is intentionally disabled; autonomous features own that surface."""
        del message, chat_id, user_id, text
        return

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            message = update.effective_message
            chat = update.effective_chat
            user = update.effective_user
            if not message or not chat or not user or bool(getattr(user, "is_bot", False)):
                return
            text = (message.text or message.caption or "").strip()
            if not text or text.startswith("/"):
                return
            private = chat.type == "private"
            group = chat.type in {"group", "supergroup"}
            if not private and not group:
                return

            explicit_voice = wants_voice(text)
            reply_context = _reply_context(message, getattr(getattr(context, "bot", None), "id", None))
            continuation = _is_continuation_request(text)
            direct = private or explicit_voice or bool(reply_context) or continuation or self._is_direct_summon(text, context, message)
            if is_cooling(f"{chat.id}:{user.id}", cooldown_seconds(chat.type, direct)):
                return

            application = getattr(context, "application", None)
            bot_data = getattr(application, "bot_data", {}) if application else {}
            storage_client = bot_data.get("storage_client")
            db = getattr(self.engine, "db", None)
            if not db:
                return

            group_id = chat.id
            group_name = (chat.title or "Midnight Oracle") if group else "Midnight Oracle DM"
            await db.upsert_member(user.id, group_id, user.username or "", user.first_name or "friend")
            profile = await self.memory.get(user.id, group_id)
            recent = await load_recent(storage_client, str(group_id))
            self.recent[group_id] = recent
            recent_context = list(recent)[-8:]
            if reply_context:
                recent_context.extend(reply_context)
            if continuation:
                recent_context.append("The member is asking for the continuation of the Oracle message they just replied to.")
            now = datetime.now()
            signal = self.mood.estimate(text)
            ctx = GroupContext(
                str(user.id), str(group_id), list(recent)[-10:], now.hour,
                now.hour >= 23 or now.hour < 3, group_name,
                profile.relationship_tier, profile.preferred_name or user.first_name or "friend",
                now_ts(), (" | ".join(list(profile.themes[:2]) + list(profile.worries[:1]))) or "none",
            )

            if private:
                try:
                    await context.bot.send_chat_action(chat_id=group_id, action="typing")
                except Exception:
                    pass
                reply = await self.replies.generate(
                    group_name, ctx.sender_name, ctx.relationship_tier, text,
                    signal.summary(), str(ctx.hour), ctx.is_late_night, ctx.memory_snippet, recent_context,
                )
                if not reply:
                    if continuation:
                        reply = _continuation_fallback(text)
                    else:
                        return
                if await self._send_reply(message, reply, chat_id=group_id, user_id=user.id, text=text, direct=True, private=True):
                    await self.memory.observe(user.id, group_id, ctx.sender_name, text, True)
                    recent.append(f"{ctx.sender_name}: {text}")
                    recent.append(f"Oracle: {reply}")
                    await save_recent(storage_client, str(group_id), recent)
                return

            if self.jokes:
                await self.jokes.observe(text, user.id, group_id)
                callback = await self.jokes.detect_callback_opportunity(text, group_id)
                if callback and not direct and not await db.cooldown_active("group", str(group_id), "ambient"):
                    await self._reply(message, callback)
                    await self.memory.observe(user.id, group_id, ctx.sender_name, text, True)
                    recent.append(f"{ctx.sender_name}: {text}")
                    recent.append(f"Oracle: {callback}")
                    await save_recent(storage_client, str(group_id), recent)
                    return

            if self.identity:
                await self.identity.update(group_id, text, signal)

            if direct:
                try:
                    await context.bot.send_chat_action(chat_id=group_id, action="typing")
                except Exception:
                    pass
                reply = await self.replies.generate(
                    group_name, ctx.sender_name, ctx.relationship_tier, text,
                    signal.summary(), str(ctx.hour), ctx.is_late_night, ctx.memory_snippet, recent_context,
                )
                if not reply:
                    if continuation:
                        reply = _continuation_fallback(text)
                    else:
                        return
                if await self._send_reply(message, reply, chat_id=group_id, user_id=user.id, text=text, direct=True, private=False):
                    await self.memory.observe(user.id, group_id, ctx.sender_name, text, True)
                    recent.append(f"{ctx.sender_name}: {text}")
                    recent.append(f"Oracle: {reply}")
                    await save_recent(storage_client, str(group_id), recent)
                return

            # Contextual sticker/reaction output is explicit-only. It can never
            # pre-empt ordinary conversation anymore.
            if self.stickers:
                media = await self.stickers.evaluate(message, signal, ctx)
                if media.should_send:
                    if media.sticker_id:
                        await message.reply_sticker(media.sticker_id, reply_to_message_id=message.message_id)
                    elif media.reaction_emoji:
                        await context.bot.set_message_reaction(group_id, message.message_id, reaction=[ReactionTypeEmoji(media.reaction_emoji)])
                    await self.stickers.record(group_id, "explicit", media.sticker_id)
                    return

            decision = await self.engine.process_message(message, ctx)
            await self.memory.observe(user.id, group_id, ctx.sender_name, text, decision.should_reply or signal.social >= 0.5)
            recent.append(f"{ctx.sender_name}: {text}")
            if decision.should_reply and decision.reply_text:
                try:
                    await context.bot.send_chat_action(chat_id=group_id, action="typing")
                except Exception:
                    pass
                if await self._send_reply(message, decision.reply_text, chat_id=group_id, user_id=user.id, text=text, direct=False, private=False):
                    recent.append(f"Oracle: {decision.reply_text}")
            await save_recent(storage_client, str(group_id), recent)
        except Exception as exc:
            application = getattr(context, "application", None)
            storage_client = getattr(application, "bot_data", {}).get("storage_client") if application else None
            await soft_alert(storage_client, "message_router", exc)

    @staticmethod
    def _is_direct_summon(text, context, message) -> bool:
        low = text.casefold().strip()
        username = str(getattr(getattr(context, "bot", None), "username", "") or "").casefold()
        if username and f"@{username}" in low:
            return True
        replied = getattr(message, "reply_to_message", None)
        replied_user = getattr(replied, "from_user", None)
        bot_id = getattr(getattr(context, "bot", None), "id", None)
        if replied_user and bot_id and getattr(replied_user, "id", None) == bot_id:
            return True
        trigger_phrases = (
            "hey oracle", "oracle suno", "oracle bhai", "oracle bro", "oracle listen",
            "midnight suno", "midnight bhai", "midnight bro", "hey midnight",
        )
        return low in {"oracle", "midnight"} or any(low == phrase or low.startswith(phrase + " ") for phrase in trigger_phrases)
