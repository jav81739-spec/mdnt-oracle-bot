"""Canonical human-chat bridge for the live Midnight Oracle runtime."""
from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

log = logging.getLogger("midnight.live_chat")

async def handle_live_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route group summons/ambient chat to the existing router and DM chat to the same AI brain."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user or user.is_bot:
        return
    text = (message.text or message.caption or "").strip()
    if not text or text.startswith("/"):
        return

    router = context.application.bot_data.get("oracle_router")
    if router is None:
        return

    if chat.type in ("group", "supergroup"):
        await router.handle(update, context)
        return

    if chat.type != "private":
        return

    # Private chat uses the same ReplyGenerator/MemoryEngine brain, not a
    # canned fallback response. The chat id is the private conversation scope.
    try:
        db = getattr(router.engine, "db", None)
        if db is None:
            return
        from midnight_oracle.handlers.message_handler import GroupContext
        from datetime import datetime
        from middleware.cooldown import cooldown_seconds, is_cooling
        from middleware.recent_buffer import load_recent, save_recent

        if is_cooling(f"{chat.id}:{user.id}", cooldown_seconds("private", True)):
            return
        profile = await router.memory.get(user.id, chat.id)
        recent = await load_recent(context.application.bot_data.get("storage_client"), str(chat.id))
        now = datetime.now()
        signal = router.mood.estimate(text)
        name = profile.preferred_name or user.first_name or "friend"
        ctx = GroupContext(
            str(user.id), str(chat.id), list(recent)[-10:], now.hour,
            now.hour >= 23 or now.hour < 3, "Private Oracle",
            profile.relationship_tier, name, now.timestamp(),
            (" | ".join(list(profile.themes[:2]) + list(profile.worries[:1]))) or "none",
        )
        reply = await router.replies.generate(
            "Private Oracle", ctx.sender_name, ctx.relationship_tier, text,
            signal.summary(), str(ctx.hour), ctx.is_late_night, ctx.memory_snippet,
        )
        if not reply:
            return
        await message.reply_text(reply)
        await router.memory.observe(user.id, chat.id, ctx.sender_name, text, True)
        recent.append(text)
        del recent[:-8]
        await save_recent(context.application.bot_data.get("storage_client"), str(chat.id), recent)
    except Exception as exc:
        log.exception("LIVE_PRIVATE_CHAT_FAILED | %r", exc)
