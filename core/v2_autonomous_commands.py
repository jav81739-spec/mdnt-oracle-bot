"""User-invoked autonomous commands; deliberately independent of the scheduler."""
from __future__ import annotations
import html
import os
from telegram.ext import CommandHandler
from .storage import storage


def _key(chat_id: int) -> str:
    return f"v2:pulse:{chat_id}"


async def settrigger(update, context):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return
    if chat.type not in ("group", "supergroup"):
        await message.reply_text("☾ /settrigger only works inside a group.", reply_to_message_id=message.message_id)
        return
    try:
        member = await chat.get_member(user.id)
        if member.status not in ("administrator", "creator"):
            await message.reply_text("🌘 Sirf group admins trigger set kar sakte hain.", reply_to_message_id=message.message_id)
            return
    except Exception:
        await message.reply_text("🌘 I couldn't verify your admin status.", reply_to_message_id=message.message_id)
        return
    word = " ".join(context.args).strip().casefold()
    if not word or len(word.split()) != 1 or len(word) > 32 or not word.isalnum():
        await message.reply_text("☾ Usage: /settrigger <one-word>", reply_to_message_id=message.message_id)
        return
    pulse = await storage.load(_key(chat.id), {})
    if not isinstance(pulse, dict):
        pulse = {}
    pulse["trigger"] = word
    await storage.set(_key(chat.id), pulse, ttl=8 * 24 * 3600)
    await message.reply_text(f"✦ Trigger set to <code>{html.escape(word)}</code>.\n\nAb ye word bolo… Midnight pop out karega. 🌙", parse_mode="HTML", reply_to_message_id=message.message_id)


async def triggerinfo(update, context):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return
    pulse = await storage.load(_key(chat.id), {})
    word = pulse.get("trigger") if isinstance(pulse, dict) else None
    word = word or os.getenv("MIDNIGHT_TRIGGER", "midnight")
    await message.reply_text(f"🌙 Trigger: <code>{html.escape(str(word))}</code>", parse_mode="HTML", reply_to_message_id=message.message_id)


def register(app):
    existing = {str(c).lower().lstrip("/") for hs in getattr(app, "handlers", {}).values() for h in hs for c in (getattr(h, "commands", None) or ())}
    for name, callback in (("settrigger", settrigger), ("triggerinfo", triggerinfo)):
        if name not in existing:
            app.add_handler(CommandHandler(name, callback), group=16)
            existing.add(name)
